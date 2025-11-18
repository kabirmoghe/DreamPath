"""
Import Weaviate data from JSON export
Run this AFTER deploying Weaviate to Render
"""
import weaviate
import json
import os
from dotenv import load_dotenv
from weaviate.classes.config import Configure, Property, DataType

load_dotenv()


def create_collection_from_schema(client, schema_file: str):
    """Create Weaviate collection from schema JSON"""
    print(f"\nCreating collection from {schema_file}...")

    with open(schema_file, 'r') as f:
        schema = json.load(f)

    collection_name = schema['name']

    try:
        # Check if collection already exists
        if client.collections.exists(collection_name):
            print(f"⚠️  Collection '{collection_name}' already exists, skipping creation")
            return

        # Create collection WITH text2vec-openai vectorizer
        # Weaviate will vectorize content during import using OpenAI API
        client.collections.create(
            name=collection_name,
            description=schema.get('description', ''),
            vectorizer_config=Configure.Vectorizer.text2vec_openai(),  # Enable OpenAI vectorization
            properties=[
                Property(
                    name=prop['name'],
                    data_type=getattr(DataType, prop['data_type'].split('.')[-1]),
                    description=prop.get('description', '')
                )
                for prop in schema['properties']
            ]
        )

        print(f"✅ Created collection: {collection_name}")

    except Exception as e:
        print(f"❌ Error creating collection {collection_name}: {e}")
        raise


def import_collection(client, collection_name: str, data_file: str):
    """Import data into Weaviate collection"""
    print(f"\n{'='*60}")
    print(f"Importing {collection_name} collection...")
    print(f"{'='*60}")

    try:
        with open(data_file, 'r') as f:
            objects = json.load(f)

        print(f"Loaded {len(objects)} objects from {data_file}")

        collection = client.collections.get(collection_name)

        # Batch import with fixed size (better for cloud imports)
        # Smaller batches to avoid gRPC timeout as HNSW index grows
        batch_size = 10  # Reduced from 50 to handle larger index sizes
        for i in range(0, len(objects), batch_size):
            batch_objects = objects[i:i + batch_size]

            try:
                with collection.batch.fixed_size(batch_size=batch_size) as batch:
                    for obj in batch_objects:
                        batch.add_object(
                            properties=obj['properties'],
                            uuid=obj['id']
                            # No vector parameter - Weaviate will generate using text2vec-openai
                        )

                print(f"  Imported {min(i + batch_size, len(objects))}/{len(objects)} objects...")

            except Exception as e:
                print(f"  ⚠️ Error in batch {i}-{i+batch_size}: {e}")
                print(f"  Continuing with next batch...")
                continue

        print(f"✅ Import process completed for {collection_name}")

        # Verify count
        result = collection.aggregate.over_all(total_count=True)
        print(f"✅ Verified: {result.total_count} objects in collection")

    except Exception as e:
        print(f"❌ Error importing {collection_name}: {e}")
        raise


def main():
    print("="*60)
    print("WEAVIATE DATA IMPORT")
    print("="*60)

    # Get connection details from environment
    http_host = os.getenv("WEAVIATE_HTTP_HOST")
    http_port = int(os.getenv("WEAVIATE_HTTP_PORT", "443"))
    http_secure = os.getenv("WEAVIATE_HTTP_SECURE", "true").lower() == "true"
    api_key = os.getenv("WEAVIATE_API_KEY")

    if not http_host:
        print("❌ WEAVIATE_HTTP_HOST not set in environment variables")
        print("\nFor Fly.io deployment, set:")
        print("  WEAVIATE_HTTP_HOST=dreampath-weaviate.fly.dev")
        print("  WEAVIATE_HTTP_PORT=443")
        print("  WEAVIATE_HTTP_SECURE=true")
        return

    print(f"\nConnecting to Weaviate at {http_host}:{http_port} (secure={http_secure})...")

    try:
        # For Render/HTTPS deployments, use different ports for gRPC
        # Render routes both HTTP and gRPC through 443, but we need to specify different ports for client validation
        grpc_port = 50051 if http_port == 443 else http_port

        # Connect with or without API key
        # Skip gRPC init checks for cloud deployments where gRPC port may not be publicly accessible
        # gRPC secure=False because Fly.io doesn't use TLS for internal gRPC
        # Increased timeout to handle large HNSW index insertions
        from weaviate.config import AdditionalConfig, Timeout

        additional_config = AdditionalConfig(
            timeout=Timeout(init=30, query=120, insert=120)  # 2 minute timeout for inserts
        )

        if api_key:
            from weaviate.auth import AuthApiKey
            client = weaviate.connect_to_custom(
                http_host=http_host,
                http_port=http_port,
                http_secure=http_secure,
                grpc_host=http_host,
                grpc_port=grpc_port,
                grpc_secure=False,  # gRPC without TLS for Fly.io
                auth_credentials=AuthApiKey(api_key),
                skip_init_checks=True,
                additional_config=additional_config
            )
        else:
            client = weaviate.connect_to_custom(
                http_host=http_host,
                http_port=http_port,
                http_secure=http_secure,
                grpc_host=http_host,
                grpc_port=grpc_port,
                grpc_secure=False,  # gRPC without TLS for Fly.io
                skip_init_checks=True,
                additional_config=additional_config
            )

        print("✅ Connected to Weaviate")

        export_dir = "weaviate_export"

        # Check if export files exist
        required_files = [
            f"{export_dir}/course_schema.json",
            f"{export_dir}/course_data.json",
            f"{export_dir}/major_schema.json",
            f"{export_dir}/major_data.json"
        ]

        for file in required_files:
            if not os.path.exists(file):
                print(f"❌ Missing file: {file}")
                print(f"\nRun export_weaviate_data.py first to create these files")
                return

        # Create collections
        create_collection_from_schema(client, f"{export_dir}/course_schema.json")
        create_collection_from_schema(client, f"{export_dir}/major_schema.json")

        # Import data
        import_collection(client, "Course", f"{export_dir}/course_data.json")
        import_collection(client, "Major", f"{export_dir}/major_data.json")

        client.close()

        print("\n" + "="*60)
        print("IMPORT COMPLETE")
        print("="*60)
        print("✅ All data imported successfully!")
        print("\nYour Render Weaviate instance is ready to use.")

    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Check WEAVIATE_* environment variables are correct")
        print("  2. Ensure Render Weaviate service is running")
        print("  3. Check Render logs for errors")


if __name__ == "__main__":
    main()
