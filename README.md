GCP TECH STACK
GCS
CLoud data fusion
apache airflow
google big query
Google functions


Cloud data fusion is used for data transformation, Cloud Storage is for storing data in a GCP bucket.

Big query. we will write querys and use looker to make dashboards and visuvalize it.

For all the data to check the airflow. we will use ---cloud composer---- 

1.Workflow is take CSV file to upload to GCP bucket
2. Data fusion is used for cleaning the data. We are using Wrangler for transforming and cleaning the CSV data from the bucket directly.
3. After data fusion used for transforming. We will create a workflow which will connect the data fusion to big query after that we will use for data flowing and after the data is completely used we will have to use lookerstudio to create a data visuzalition report.


4. Using Apache Airflow to automate all the pipline(we will use composer to create a DAG(It is a Airflow workflow.))


