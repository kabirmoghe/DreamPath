"""
Export Weaviate data to JSON for migration to Render
Run this BEFORE shutting down local Weaviate Docker container
"""
import weaviate
import json
import os
from datetime import datetime
from uuid import UUID
from dotenv import load_dotenv

load_dotenv()


def serialize_value(value):
    """Convert non-JSON-serializable types to strings"""
    if isinstance(value, datetime):
        return value.isoformat()  # RFC3339 format with 'T' separator
    elif isinstance(value, UUID):
        return str(value)
    elif isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [serialize_value(item) for item in value]
    return value

def export_collection(client, collection_name: str, output_file: str):
    """Export a Weaviate collection to JSON"""
    print(f"\n{'='*60}")
    print(f"Exporting {collection_name} collection...")
    print(f"{'='*60}")

    try:
        collection = client.collections.get(collection_name)

        # Fetch all objects (paginated if needed)
        objects = []
        offset = 0
        limit = 100

        while True:
            result = collection.query.fetch_objects(
                limit=limit,
                offset=offset,
                return_properties=None,  # Get all properties
                include_vector=True  # IMPORTANT: Include vectors in export
            )

            if not result.objects:
                break

            for obj in result.objects:
                # Serialize properties to handle UUID, datetime, etc.
                serialized_properties = serialize_value(obj.properties)

                # Extract vector (it's a dict with named vectors in v4)
                vector_data = None
                if hasattr(obj, 'vector') and obj.vector:
                    if isinstance(obj.vector, dict):
                        vector_data = obj.vector.get("default", list(obj.vector.values())[0] if obj.vector else None)
                    else:
                        vector_data = obj.vector

                objects.append({
                    "id": str(obj.uuid),
                    "properties": serialized_properties,
                    "vector": vector_data
                })

            offset += limit
            print(f"  Exported {len(objects)} objects so far...")

            if len(result.objects) < limit:
                break

        # Save to JSON
        with open(output_file, 'w') as f:
            json.dump(objects, f, indent=2)

        print(f"✅ Exported {len(objects)} objects to {output_file}")
        print(f"   File size: {os.path.getsize(output_file) / 1024 / 1024:.2f} MB")

        return len(objects)

    except Exception as e:
        print(f"❌ Error exporting {collection_name}: {e}")
        return 0


def export_schema(client, collection_name: str, output_file: str):
    """Export collection schema"""
    print(f"\nExporting {collection_name} schema...")

    try:
        collection = client.collections.get(collection_name)
        config = collection.config.get()

        schema = {
            "name": config.name,
            "description": config.description,
            "properties": [
                {
                    "name": prop.name,
                    "data_type": str(prop.data_type),
                    "description": prop.description
                }
                for prop in config.properties
            ],
            "vectorizer_config": {
                "vectorizer": str(config.vectorizer_config) if config.vectorizer_config else None
            }
        }

        with open(output_file, 'w') as f:
            json.dump(schema, f, indent=2)

        print(f"✅ Schema saved to {output_file}")

    except Exception as e:
        print(f"❌ Error exporting schema: {e}")


def main():
    print("="*60)
    print("WEAVIATE DATA EXPORT")
    print("="*60)

    # Check if Weaviate is running
    http_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
    http_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))

    print(f"\nConnecting to Weaviate at {http_host}:{http_port}...")

    try:
        client = weaviate.connect_to_custom(
            http_host=http_host,
            http_port=http_port,
            http_secure=False,
            grpc_host=os.getenv("WEAVIATE_GRPC_HOST", "localhost"),
            grpc_port=int(os.getenv("WEAVIATE_GRPC_PORT", "50051")),
            grpc_secure=False,
        )

        print("✅ Connected to Weaviate")

        # Create export directory
        export_dir = "weaviate_export"
        os.makedirs(export_dir, exist_ok=True)

        # Export Course collection
        course_count = export_collection(
            client,
            "Course",
            f"{export_dir}/course_data.json"
        )
        export_schema(
            client,
            "Course",
            f"{export_dir}/course_schema.json"
        )

        # Export Major collection
        major_count = export_collection(
            client,
            "Major",
            f"{export_dir}/major_data.json"
        )
        export_schema(
            client,
            "Major",
            f"{export_dir}/major_schema.json"
        )

        client.close()

        print("\n" + "="*60)
        print("EXPORT COMPLETE")
        print("="*60)
        print(f"✅ Courses exported: {course_count}")
        print(f"✅ Majors exported: {major_count}")
        print(f"\nExported files in '{export_dir}/' directory:")
        print(f"  - course_data.json")
        print(f"  - course_schema.json")
        print(f"  - major_data.json")
        print(f"  - major_schema.json")
        print(f"\n⚠️  Keep these files safe! You'll need them for import.")

    except Exception as e:
        print(f"\n❌ Failed to connect to Weaviate: {e}")
        print("\nMake sure Weaviate is running:")
        print("  docker compose up -d")


if __name__ == "__main__":
    main()
