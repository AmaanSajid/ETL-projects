from google.cloud import bigquery
from google.oauth2 import service_account
from google.api_core import retry

# Use your existing credentials
credentials = service_account.Credentials.from_service_account_file(
    "news-analysis-439620-f63dbe7dd613.json"
)

class BigQueryManager:
    def __init__(self, project_id):
        self.client = bigquery.Client(credentials=credentials, project=project_id)
        self.project_id = project_id
        
    def create_dataset(self, dataset_id, location="US", description=None):
        """
        Create a BigQuery dataset with specified location and description
        
        Args:
            dataset_id (str): ID of the dataset to create
            location (str): Geographic location of the dataset (default: "US")
            description (str, optional): Description of the dataset
        """
        dataset_ref = self.client.dataset(dataset_id)
        try:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = location
            if description:
                dataset.description = description
                
            # Add default expiration for tables (optional, set to None for no expiration)
            dataset.default_table_expiration_ms = None
            
            # Enable automatic table deletion when empty (optional)
            dataset.delete_contents_on_dataset_deletion = True
            
            dataset = self.client.create_dataset(dataset, timeout=30)
            print(f"Dataset {dataset_id} created successfully in {location}")
            return dataset
            
        except Exception as e:
            if "Already Exists" in str(e):
                print(f"Dataset {dataset_id} already exists")
                return self.client.get_dataset(dataset_ref)
            else:
                print(f"Error creating dataset {dataset_id}: {e}")
                raise
    
    @retry.Retry()
    def create_table(self, dataset_id, table_id, clustering_fields=None):
        """
        Create a BigQuery table with the news articles schema
        
        Args:
            dataset_id (str): ID of the dataset to create the table in
            table_id (str): ID of the table to create
            clustering_fields (list, optional): Fields to cluster the table by
        """
        # Define the schema
        schema = [
            bigquery.SchemaField("category", "STRING", mode="REQUIRED",
                               description="News article category"),
            bigquery.SchemaField("headline", "STRING", mode="REQUIRED",
                               description="Article headline"),
            bigquery.SchemaField("authors", "STRING", mode="REPEATED",
                               description="List of article authors"),
            bigquery.SchemaField("link", "STRING", mode="REQUIRED",
                               description="URL link to the article"),
            bigquery.SchemaField("short_description", "STRING", mode="REQUIRED",
                               description="Brief description of the article"),
            bigquery.SchemaField("date", "DATE", mode="REQUIRED",
                               description="Article publication date"),
            bigquery.SchemaField("publish_timestamp", "TIMESTAMP", mode="REQUIRED",
                               description="Timestamp when article was published"),
            bigquery.SchemaField("process_timestamp", "TIMESTAMP", mode="REQUIRED",
                               description="Timestamp when article was processed")
        ]
        
        # Create table reference
        table_ref = self.client.dataset(dataset_id).table(table_id)
        
        try:
            # Create table with additional configuration
            table = bigquery.Table(table_ref, schema=schema)
            
            # Add clustering if specified
            if clustering_fields:
                table.clustering_fields = clustering_fields
            
            # Add partitioning by date
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="date"  # Partition by the date field
            )
            
            # Create the table
            table = self.client.create_table(table)
            print(f"Table {dataset_id}.{table_id} created successfully")
            return table
            
        except Exception as e:
            if "Already Exists" in str(e):
                print(f"Table {dataset_id}.{table_id} already exists")
                return self.client.get_table(table_ref)
            else:
                print(f"Error creating table {dataset_id}.{table_id}: {e}")
                raise
    
    def get_table_info(self, dataset_id, table_id):
        """Get information about a specific table"""
        try:
            table_ref = self.client.dataset(dataset_id).table(table_id)
            table = self.client.get_table(table_ref)
            
            info = {
                "table_id": table.table_id,
                "num_rows": table.num_rows,
                "num_bytes": table.num_bytes,
                "schema": [field.to_api_repr() for field in table.schema],
                "partitioning": table.time_partitioning,
                "clustering": table.clustering_fields,
                "created": table.created,
                "modified": table.modified
            }
            return info
        except Exception as e:
            print(f"Error getting table info: {e}")
            raise

def setup_bigquery():
    # Your GCP project settings
    project_id = "news-analysis-439620"
    dataset_id = "news_articles"
    table_id = "articles"
    
    # Initialize BigQuery manager
    bq_manager = BigQueryManager(project_id)
    
    # Create dataset with description
    dataset = bq_manager.create_dataset(
        dataset_id,
        description="News articles dataset containing categorized news data"
    )
    
    # Create table with clustering
    table = bq_manager.create_table(
        dataset_id,
        table_id,
        clustering_fields=["category"]  # Cluster by category for better query performance
    )
    
    # Print table information
    table_info = bq_manager.get_table_info(dataset_id, table_id)
    print("\nTable Information:")
    print(f"Number of rows: {table_info['num_rows']}")
    print(f"Size in bytes: {table_info['num_bytes']}")
    print(f"Created: {table_info['created']}")

if __name__ == "__main__":
    setup_bigquery()