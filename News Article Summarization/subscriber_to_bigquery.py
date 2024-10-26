from google.cloud import pubsub_v1, bigquery
from google.oauth2 import service_account
import json
from datetime import datetime

# Use your existing credentials
credentials = service_account.Credentials.from_service_account_file(
    "news-analysis-439620-f63dbe7dd613.json"
)

class NewsSubscriberToBigQuery:
    def __init__(self, project_id, subscription_id, dataset_id, table_id):
        self.subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
        self.subscription_path = self.subscriber.subscription_path(
            project_id, subscription_id
        )
        self.bq_client = bigquery.Client(credentials=credentials, project=project_id)
        self.table_id = f"{project_id}.{dataset_id}.{table_id}"
    
    def process_message(self, message):
        """Process and store message in BigQuery"""
        try:
            # Split the JSONL data into lines and process each line
            lines = message.data.decode("utf-8").strip().split('\n')
            rows = []
            
            for line in lines:
                if not line:  # Skip empty lines
                    continue
                    
                # Parse each line as a JSON object
                data = json.loads(line)
                
                # Convert date string to datetime object
                date_obj = datetime.strptime(data["date"], "%Y-%m-%d").date()
                
                # Ensure authors is a list
                authors = data["authors"]
                if isinstance(authors, str):
                    # If authors is a comma-separated string, split it into a list
                    authors = [author.strip() for author in authors.split(',')]
                elif not isinstance(authors, list):
                    # If authors is neither a string nor a list, wrap it in a list
                    authors = [str(authors)]
                
                # Prepare row for BigQuery
                row = {
                    "category": data["category"],
                    "headline": data["headline"],
                    "authors": authors,  # Now properly formatted as a list
                    "link": data["link"],
                    "short_description": data["short_description"],
                    "date": date_obj.isoformat(),  # Convert date to ISO format string
                    "publish_timestamp": datetime.now().isoformat(),  # Convert to ISO format string
                    "process_timestamp": datetime.now().isoformat()  # Convert to ISO format string
                }
                rows.append(row)
            
            # Batch insert rows into BigQuery
            if rows:
                errors = self.bq_client.insert_rows_json(self.table_id, rows)
                
                if errors == []:
                    print(f"Successfully inserted {len(rows)} articles")
                    message.ack()
                else:
                    print(f"Error inserting articles: {errors}")
                    message.nack()
            else:
                print("No valid data found in message")
                message.ack()  # Acknowledge empty messages to prevent reprocessing
                
        except Exception as e:
            print(f"Error processing message: {e}")
            message.nack()
    
    def receive_messages(self, timeout=None):
        """Start receiving messages"""
        streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path, callback=self.process_message
        )
        print(f"Listening for messages on {self.subscription_path}")
        
        try:
            streaming_pull_future.result(timeout=timeout)
        except TimeoutError:
            streaming_pull_future.cancel()
            streaming_pull_future.result()
        except Exception as e:
            streaming_pull_future.cancel()
            print(f"Error receiving messages: {e}")

def main():
    # Your GCP project settings
    project_id = "news-analysis-439620"
    subscription_id = "news-dataset-sub"
    dataset_id = "news_articles"
    table_id = "articles"
    
    # Initialize subscriber
    subscriber = NewsSubscriberToBigQuery(
        project_id, subscription_id, dataset_id, table_id
    )
    
    # Start receiving messages with a timeout of 60 seconds
    subscriber.receive_messages(timeout=60)

if __name__ == "__main__":
    main()