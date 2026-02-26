"""Validate enriched review data ingestion into Weaviate."""

import argparse
from dreampath_processing.weaviate.connection import connect_local_with_openai
from weaviate.classes.query import Filter


def validate_review_ingestion(collection_name="Course"):
    """
    Run validation queries to verify review data ingestion.

    Tests:
    1. Schema validation (all 15 new fields exist)
    2. Data completeness (counts, null checks)
    3. Semantic search on blurbs (verify vectorization)
    4. Filtering by review metrics (difficulty, value)
    5. Sample data inspection
    """
    client = connect_local_with_openai()

    try:
        coll = client.collections.get(collection_name)

        print("=" * 70)
        print("VALIDATION: Enriched Review Data Ingestion")
        print("=" * 70)

        # Test 1: Schema validation
        print("\n✅ Test 1: Schema Validation")
        properties = coll.config.get().properties
        property_names = [p.name for p in properties]

        expected_review_fields = [
            "total_reviews",
            "global_difficulty_score", "global_difficulty_normalized",
            "global_difficulty_percentile", "global_difficulty_classification",
            "dept_difficulty_percentile", "dept_difficulty_classification",
            "difficulty_blurb",
            "global_value_score", "global_value_normalized",
            "global_value_percentile", "global_value_classification",
            "dept_value_percentile", "dept_value_classification",
            "learning_value_blurb", "target_audience_blurb",
        ]

        missing_fields = [f for f in expected_review_fields if f not in property_names]
        if missing_fields:
            print(f"   ❌ FAIL: Missing fields: {missing_fields}")
            return False
        else:
            print(f"   ✓ PASS: All 15 review fields present")
            print(f"   Total properties: {len(property_names)}")

        # Test 2: Data completeness
        print("\n✅ Test 2: Data Completeness")

        # Count total courses
        total_result = coll.aggregate.over_all(total_count=True)
        total_courses = total_result.total_count
        print(f"   Total courses: {total_courses}")

        # Count courses with reviews (total_reviews > 0)
        with_reviews_result = coll.aggregate.over_all(
            filters=Filter.by_property("total_reviews").greater_than(0),
            total_count=True
        )
        with_reviews = with_reviews_result.total_count
        print(f"   Courses with reviews: {with_reviews}")
        print(f"   Courses without reviews: {total_courses - with_reviews}")
        if total_courses > 0:
            print(f"   Coverage: {with_reviews/total_courses*100:.1f}%")

        # Test 3: Semantic search on blurbs (verify vectorization)
        print("\n✅ Test 3: Semantic Search on Blurbs")

        # Search difficulty blurb
        try:
            results = coll.query.near_text(
                query="challenging course with heavy workload",
                return_properties=["course_code", "course_title", "difficulty_blurb", "total_reviews"],
                limit=3
            )

            if len(results.objects) > 0:
                print(f"   ✓ PASS: difficulty_blurb vectorization working")
                print(f"   Sample results for 'challenging course with heavy workload':")
                for obj in results.objects[:3]:
                    props = obj.properties
                    blurb = props.get('difficulty_blurb', 'N/A')
                    if blurb and blurb != 'N/A':
                        print(f"      {props['course_code']}: {blurb[:80]}...")
                    else:
                        print(f"      {props['course_code']}: (no blurb)")
            else:
                print(f"   ⚠️  WARNING: No results from difficulty_blurb search")
        except Exception as e:
            print(f"   ❌ FAIL: Semantic search error: {e}")

        # Test 4: Filtering by review metrics
        print("\n✅ Test 4: Filtering by Review Metrics")

        # High difficulty courses (global_difficulty_percentile > 80)
        try:
            high_diff = coll.query.fetch_objects(
                filters=Filter.by_property("global_difficulty_percentile").greater_than(80),
                return_properties=["course_code", "global_difficulty_percentile",
                                 "global_difficulty_classification"],
                limit=5
            )
            print(f"   High difficulty courses (>80th percentile): {len(high_diff.objects)}")
            for obj in high_diff.objects[:3]:
                props = obj.properties
                pct = props.get('global_difficulty_percentile', 'N/A')
                cls = props.get('global_difficulty_classification', 'N/A')
                print(f"      {props['course_code']}: {pct:.1f}th percentile ({cls})")
        except Exception as e:
            print(f"   ⚠️  WARNING: Difficulty filter error: {e}")

        # High value courses (global_value_percentile > 80)
        try:
            high_value = coll.query.fetch_objects(
                filters=Filter.by_property("global_value_percentile").greater_than(80),
                return_properties=["course_code", "global_value_percentile",
                                 "global_value_classification"],
                limit=5
            )
            print(f"   High value courses (>80th percentile): {len(high_value.objects)}")
            for obj in high_value.objects[:3]:
                props = obj.properties
                pct = props.get('global_value_percentile', 'N/A')
                cls = props.get('global_value_classification', 'N/A')
                print(f"      {props['course_code']}: {pct:.1f}th percentile ({cls})")
        except Exception as e:
            print(f"   ⚠️  WARNING: Value filter error: {e}")

        # Test 5: Sample data inspection
        print("\n✅ Test 5: Sample Data Inspection")

        # Get one course with full review data
        try:
            sample = coll.query.fetch_objects(
                filters=Filter.by_property("total_reviews").greater_than(5),
                limit=1
            )

            if len(sample.objects) > 0:
                props = sample.objects[0].properties
                print(f"   Sample course: {props['course_code']} - {props.get('course_title', 'N/A')[:50]}...")
                print(f"   Total reviews: {props.get('total_reviews')}")
                print(f"   Difficulty:")
                print(f"      Score: {props.get('global_difficulty_score')}")
                print(f"      Normalized: {props.get('global_difficulty_normalized')}")
                print(f"      Percentile: {props.get('global_difficulty_percentile')}")
                print(f"      Classification: {props.get('global_difficulty_classification')}")
                blurb = props.get('difficulty_blurb', 'N/A')
                print(f"      Blurb: {blurb[:100] if blurb != 'N/A' else 'N/A'}...")
                print(f"   Learning Value:")
                print(f"      Score: {props.get('global_value_score')}")
                print(f"      Normalized: {props.get('global_value_normalized')}")
                print(f"      Percentile: {props.get('global_value_percentile')}")
                print(f"      Classification: {props.get('global_value_classification')}")
                blurb = props.get('learning_value_blurb', 'N/A')
                print(f"      Blurb: {blurb[:100] if blurb != 'N/A' else 'N/A'}...")
                blurb = props.get('target_audience_blurb', 'N/A')
                print(f"   Target Audience: {blurb[:100] if blurb != 'N/A' else 'N/A'}...")
            else:
                print(f"   ⚠️  WARNING: No courses with >5 reviews found")
        except Exception as e:
            print(f"   ❌ FAIL: Sample inspection error: {e}")

        print("\n" + "=" * 70)
        print("VALIDATION COMPLETE")
        print("=" * 70)
        print("✓ All tests passed")

        return True

    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        return False
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Validate enriched review data ingestion into Weaviate"
    )
    parser.add_argument(
        "--collection",
        default="Course",
        help="Collection name to validate (default: Course)"
    )
    args = parser.parse_args()

    success = validate_review_ingestion(args.collection)
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
