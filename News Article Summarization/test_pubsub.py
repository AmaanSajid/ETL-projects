# publisher.py
from google.cloud import pubsub_v1
import json
import time
from google.cloud import storage
from google.oauth2 import service_account

# Set your Google Cloud credentials
credentials = service_account.Credentials.from_service_account_file("news-analysis-439620-f63dbe7dd613.json")

class NewsPublisher:
    def __init__(self, project_id, topic_id):
        self.publisher = pubsub_v1.PublisherClient(credentials=credentials)
        self.topic_path = self.publisher.topic_path(project_id, topic_id)
        self.storage_client = storage.Client(credentials=credentials)
        
    def check_or_create_topic(self):
        """Check if a Pub/Sub topic exists, create if it doesn't"""
        try:
            self.publisher.get_topic(request={"topic": self.topic_path})
            print(f"Topic {self.topic_path} already exists.")
        except Exception:
            self.publisher.create_topic(request={"name": self.topic_path})
            print(f"Created topic: {self.topic_path}")
    
    def publish_message(self, articles):
        """Publish articles in JSONL format"""
        try:
            # Convert articles to JSONL format
            jsonl_data = "\n".join(json.dumps(article) for article in articles)
            # Convert string to bytes
            articles_bytes = jsonl_data.encode("utf-8")
            
            # Publish message
            future = self.publisher.publish(self.topic_path, articles_bytes)
            message_id = future.result()
            
            print(f"Published message ID: {message_id} with {len(articles)} articles")
            return message_id
            
        except Exception as e:
            print(f"An error occurred: {e}")
            return None
    
    def publish_from_file(self, file_path, batch_size=10):
        """Publish articles from a JSONL file in batches"""
        try:
            current_batch = []
            with open(file_path, 'r') as f:
                for line in f:
                    try:
                        article = json.loads(line.strip())
                        current_batch.append(article)
                        
                        if len(current_batch) >= batch_size:
                            self.publish_message(current_batch)
                            current_batch = []
                            time.sleep(0.1)
                    except json.JSONDecodeError as e:
                        print(f"Error parsing line: {e}")
                        continue
                
                # Publish remaining articles
                if current_batch:
                    self.publish_message(current_batch)
                    
        except Exception as e:
            print(f"Error publishing from file: {e}")
    
    def publish_from_gcs(self, bucket_name, blob_name, batch_size=10):
        """Publish articles from a GCS bucket in JSONL format"""
        try:
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # Download as string and split into lines
            content = blob.download_as_string().decode('utf-8')
            lines = content.strip().split('\n')
            
            current_batch = []
            for line in lines:
                try:
                    article = json.loads(line)
                    current_batch.append(article)
                    
                    if len(current_batch) >= batch_size:
                        self.publish_message(current_batch)
                        current_batch = []
                        time.sleep(0.1)
                except json.JSONDecodeError as e:
                    print(f"Error parsing line: {e}")
                    continue
            
            # Publish remaining articles
            if current_batch:
                self.publish_message(current_batch)
                
        except Exception as e:
            print(f"Error publishing from GCS: {e}")

class NewsSubscriber:
    def __init__(self, project_id, subscription_id, timeout=None):
        self.subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
        self.subscription_path = self.subscriber.subscription_path(
            project_id, subscription_id
        )
        self.timeout = timeout
    
    def check_or_create_subscription(self, topic_path):
        """Check if a subscription exists, create if it doesn't"""
        try:
            self.subscriber.get_subscription(request={"subscription": self.subscription_path})
            print(f"Subscription {self.subscription_path} already exists.")
        except Exception:
            self.subscriber.create_subscription(
                request={"name": self.subscription_path, "topic": topic_path}
            )
            print(f"Created subscription: {self.subscription_path}")
    
    def callback(self, message):
        """Process received messages in JSONL format"""
        try:
            # Split the message data into lines and process each line
            lines = message.data.decode("utf-8").strip().split('\n')
            
            for line in lines:
                if not line:  # Skip empty lines
                    continue
                    
                # Parse each line as a JSON object
                data = json.loads(line)
                print(f"Received article: {data['headline']}")
            
            # Acknowledge the message after processing all articles
            message.ack()
            
        except Exception as e:
            print(f"Error processing message: {e}")
            message.nack()
    
    def receive_messages(self):
        """Start receiving messages"""
        streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path, callback=self.callback
        )
        print(f"Listening for messages on {self.subscription_path}")
        
        try:
            streaming_pull_future.result(timeout=self.timeout)
        except TimeoutError:
            streaming_pull_future.cancel()
            streaming_pull_future.result()
        except Exception as e:
            streaming_pull_future.cancel()
            print(f"Error receiving messages: {e}")

def main():
    # Your GCP project settings
    project_id = "news-analysis-439620"
    topic_id = "news-dataset"
    subscription_id = "news-dataset-sub"
    
    # Initialize publisher
    publisher = NewsPublisher(project_id, topic_id)
    publisher.check_or_create_topic()
    
    # Initialize subscriber
    subscriber = NewsSubscriber(project_id, subscription_id)
    subscriber.check_or_create_subscription(publisher.topic_path)
    
    # Example: Publish from local file
    publisher.publish_from_file("test.json", batch_size=10)
    
    # Example: Publish from GCS
    publisher.publish_from_gcs("news-dataset-csv", "test.json", batch_size=10)
    
    # Start receiving messages
    subscriber.receive_messages()

if __name__ == "__main__":
    main()