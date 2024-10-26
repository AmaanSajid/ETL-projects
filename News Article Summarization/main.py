# Import required libraries
from google.cloud import storage, bigquery, pubsub_v1
from google.cloud import aiplatform
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
import json
import datetime
from typing import Dict, List
import pandas as pd
from google.oauth2 import service_account

# Configuration
PROJECT_ID = "news-analysis-439620"
BUCKET_NAME = "news-dataset-csv"
DATASET_ID = "news_articles_dataset"
PUBSUB_TOPIC = "news-articles-topic"

class NewsArticleProcessor:
    def __init__(self):
        # Initialize GCP clients
        self.storage_client = storage.Client()
        self.bigquery_client = bigquery.Client()
        self.publisher = pubsub_v1.PublisherClient()
        
        # Initialize Vertex AI
        aiplatform.init(project=PROJECT_ID, location='us-central1')
    
    def process_json_file(self, json_data: List[Dict]):
        """Process JSON data and upload to Cloud Storage"""
        # Group articles by date for partitioning
        articles_by_date = {}
        for article in json_data:
            date = datetime.datetime.strptime(article['date'], '%Y-%m-%d').strftime('%Y/%m/%d')
            if date not in articles_by_date:
                articles_by_date[date] = []
            articles_by_date[date].append(article)
        
        # Upload to Cloud Storage with date-based partitioning
        bucket = self.storage_client.bucket(BUCKET_NAME)
        for date, articles in articles_by_date.items():
            blob = bucket.blob(f'raw/{date}/articles.json')
            blob.upload_from_string(
                json.dumps(articles),
                content_type='application/json'
            )
            
            # Publish to Pub/Sub for processing
            topic_path = self.publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC)
            for article in articles:
                self.publisher.publish(
                    topic_path, 
                    json.dumps(article).encode('utf-8')
                )

class ArticleEnrichmentPipeline(beam.PipelineOptions):
    """Apache Beam pipeline for article enrichment"""
    
    @staticmethod
    def enrich_with_llm(article: Dict) -> Dict:
        """Enrich article with LLM-generated content"""
        
        # Create prompt for article analysis
        prompt = f"""
        Analyze this news article:
        Headline: {article['headline']}
        Description: {article['short_description']}
        
        Please provide:
        1. A comprehensive summary (150-200 words)
        2. Main topics and subtopics
        3. Key entities mentioned (people, organizations, locations)
        4. Sentiment analysis
        5. Related topics to explore
        
        Format the response as JSON.
        """
        
        # Get LLM response using Vertex AI
        model = aiplatform.TextGenerationModel.from_pretrained("Gemini-1.5-pro")
        response = model.predict(prompt).text
        
        # Parse LLM response and add to article
        enriched_data = json.loads(response)
        article.update({
            'enhanced_summary': enriched_data['summary'],
            'topics': enriched_data['topics'],
            'entities': enriched_data['entities'],
            'sentiment': enriched_data['sentiment'],
            'related_topics': enriched_data['related_topics']
        })
        
        return article

    def run_pipeline(self):
        """Execute the Beam pipeline"""
        pipeline_options = PipelineOptions(
            runner='DataflowRunner',
            project=PROJECT_ID,
            job_name='news-article-enrichment',
            temp_location=f'gs://{BUCKET_NAME}/temp'
        )
        
        with beam.Pipeline(options=pipeline_options) as pipeline:
            articles = (
                pipeline
                | 'Read from PubSub' >> beam.io.ReadFromPubSub(
                    topic=f'projects/{PROJECT_ID}/topics/{PUBSUB_TOPIC}'
                )
                | 'Parse JSON' >> beam.Map(json.loads)
                | 'Enrich with LLM' >> beam.Map(self.enrich_with_llm)
                | 'Write to BigQuery' >> beam.io.WriteToBigQuery(
                    table=f'{PROJECT_ID}:{DATASET_ID}.articles',
                    schema=self.get_bigquery_schema(),
                    write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                    create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
                )
            )

    @staticmethod
    def get_bigquery_schema():
        """Define BigQuery schema for enriched articles"""
        return {
            'fields': [
                {'name': 'category', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'headline', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'authors', 'type': 'STRING', 'mode': 'REPEATED'},
                {'name': 'link', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'short_description', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'date', 'type': 'DATE', 'mode': 'REQUIRED'},
                {'name': 'enhanced_summary', 'type': 'STRING', 'mode': 'NULLABLE'},
                {'name': 'topics', 'type': 'STRING', 'mode': 'REPEATED'},
                {'name': 'entities', 'type': 'RECORD', 'mode': 'NULLABLE', 'fields': [
                    {'name': 'people', 'type': 'STRING', 'mode': 'REPEATED'},
                    {'name': 'organizations', 'type': 'STRING', 'mode': 'REPEATED'},
                    {'name': 'locations', 'type': 'STRING', 'mode': 'REPEATED'}
                ]},
                {'name': 'sentiment', 'type': 'RECORD', 'mode': 'NULLABLE', 'fields': [
                    {'name': 'score', 'type': 'FLOAT', 'mode': 'REQUIRED'},
                    {'name': 'magnitude', 'type': 'FLOAT', 'mode': 'REQUIRED'}
                ]},
                {'name': 'related_topics', 'type': 'STRING', 'mode': 'REPEATED'}
            ]
        }

# Example usage and utility functions
def create_bigquery_views():
    """Create useful BigQuery views for analysis"""
    client = bigquery.Client()
    
    # Top topics by date
    top_topics_query = """
    CREATE OR REPLACE VIEW `{PROJECT_ID}.{DATASET_ID}.top_topics_by_date` AS
    SELECT 
        date,
        topic,
        COUNT(*) as article_count,
        AVG(sentiment.score) as avg_sentiment
    FROM `{PROJECT_ID}.{DATASET_ID}.articles`
    CROSS JOIN UNNEST(topics) as topic
    GROUP BY date, topic
    ORDER BY date DESC, article_count DESC
    """
    
    # Entity co-occurrence
    entity_network_query = """
    CREATE OR REPLACE VIEW `{PROJECT_ID}.{DATASET_ID}.entity_network` AS
    SELECT 
        e1.name as entity1,
        e2.name as entity2,
        COUNT(*) as co_occurrences
    FROM `{PROJECT_ID}.{DATASET_ID}.articles`,
    UNNEST(entities.people || entities.organizations) as e1,
    UNNEST(entities.people || entities.organizations) as e2
    WHERE e1.name < e2.name
    GROUP BY entity1, entity2
    HAVING co_occurrences > 1
    ORDER BY co_occurrences DESC
    """
    
    client.query(top_topics_query)
    client.query(entity_network_query)

def main():
    # Initialize processor
    processor = NewsArticleProcessor()
    
    # Load your JSON data
    with open('your_news_data.json', 'r') as f:
        news_data = json.load(f)
    
    # Process and upload data
    processor.process_json_file(news_data)
    
    # Run enrichment pipeline
    pipeline = ArticleEnrichmentPipeline()
    pipeline.run_pipeline()
    
    # Create analysis views
    create_bigquery_views()

if __name__ == "__main__":
    main()