"""Merge course catalog with enriched review data for Weaviate ingestion."""

import argparse
import pandas as pd
from pathlib import Path


def merge_course_catalog_with_reviews(
    catalog_csv: str | Path,
    reviews_csv: str | Path,
    output_csv: str | Path,
    filter_department: str | None = None
) -> pd.DataFrame:
    """
    Merge course catalog with enriched review data.

    Args:
        catalog_csv: Path to all_courses.csv (course catalog)
        reviews_csv: Path to enriched_courses.csv (review data)
        output_csv: Path to write merged CSV
        filter_department: Optional department filter (e.g., 'COSC' for CS only)

    Returns:
        Merged DataFrame
    """
    print("=" * 70)
    print("MERGING COURSE CATALOG WITH ENRICHED REVIEW DATA")
    print("=" * 70)

    # Load catalog
    print(f"\n📚 Loading catalog: {catalog_csv}")
    catalog_df = pd.read_csv(catalog_csv)
    print(f"   Catalog courses: {len(catalog_df)}")

    # Filter by department if requested
    if filter_department:
        print(f"\n🔍 Filtering to department: {filter_department}")
        catalog_df = catalog_df[catalog_df['department'] == filter_department]
        print(f"   Filtered courses: {len(catalog_df)}")

    # Load reviews
    print(f"\n⭐ Loading reviews: {reviews_csv}")
    reviews_df = pd.read_csv(reviews_csv)
    print(f"   Courses with reviews: {len(reviews_df)}")

    # Normalize course_code for matching (uppercase, strip whitespace)
    print("\n🔄 Normalizing course codes for matching...")
    catalog_df['course_code_norm'] = catalog_df['course_code'].str.strip().str.upper()
    reviews_df['course_code_norm'] = reviews_df['course_code'].str.strip().str.upper()

    # Left join: Keep all catalog courses, add review data where available
    print("\n🔗 Performing LEFT JOIN on course_code...")
    merged_df = catalog_df.merge(
        reviews_df,
        on='course_code_norm',
        how='left',
        suffixes=('', '_review')
    )

    # Handle duplicate columns
    duplicate_cols = [col for col in merged_df.columns if col.endswith('_review')]
    if duplicate_cols:
        print(f"\n⚙️  Resolving duplicate columns: {', '.join(duplicate_cols)}")

        # Check for department mismatches
        if 'department_review' in merged_df.columns:
            mismatches = merged_df[
                (merged_df['department_review'].notna()) &
                (merged_df['department'] != merged_df['department_review'])
            ]
            if len(mismatches) > 0:
                print(f"   ⚠️  Warning: {len(mismatches)} department mismatches detected")
                print(f"   Sample mismatches:")
                for _, row in mismatches.head(5).iterrows():
                    print(f"      {row['course_code']}: {row['department']} vs {row['department_review']}")

        # Drop duplicate columns (prefer catalog versions)
        merged_df.drop(columns=duplicate_cols, inplace=True, errors='ignore')

    # Drop normalization column
    merged_df.drop(columns=['course_code_norm'], inplace=True, errors='ignore')

    # Statistics
    courses_with_reviews = merged_df['total_reviews'].notna().sum()
    courses_without_reviews = len(merged_df) - courses_with_reviews

    print("\n" + "=" * 70)
    print("MERGE STATISTICS")
    print("=" * 70)
    print(f"Total courses in catalog: {len(catalog_df)}")
    print(f"Courses with review data: {courses_with_reviews}")
    print(f"Courses without review data: {courses_without_reviews}")
    if len(catalog_df) > 0:
        print(f"Review coverage: {courses_with_reviews/len(merged_df)*100:.1f}%")

    # Check for reviews that didn't match catalog
    catalog_codes = set(catalog_df['course_code_norm'])
    review_codes = set(reviews_df['course_code_norm'])
    unmatched_reviews = review_codes - catalog_codes

    if unmatched_reviews:
        print(f"\n⚠️  Warning: {len(unmatched_reviews)} reviews didn't match catalog")
        print("Sample unmatched courses:")
        unmatched_df = reviews_df[reviews_df['course_code_norm'].isin(unmatched_reviews)]
        for _, row in unmatched_df.head(10).iterrows():
            print(f"   {row['course_code']} ({row['department']})")

    # Write output
    print(f"\n💾 Writing merged data to: {output_csv}")
    output_path = Path(output_csv)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    merged_df.to_csv(output_path, index=False)
    print("   ✓ Complete")

    return merged_df


def main():
    parser = argparse.ArgumentParser(
        description="Merge course catalog with enriched review data"
    )
    parser.add_argument(
        "--catalog",
        required=True,
        help="Path to course catalog CSV (all_courses.csv)"
    )
    parser.add_argument(
        "--reviews",
        required=True,
        help="Path to enriched reviews CSV (enriched_courses.csv)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output merged CSV"
    )
    parser.add_argument(
        "--filter-department",
        default=None,
        help="Optional department filter (e.g., COSC for CS only)"
    )

    args = parser.parse_args()

    merged_df = merge_course_catalog_with_reviews(
        catalog_csv=args.catalog,
        reviews_csv=args.reviews,
        output_csv=args.output,
        filter_department=args.filter_department
    )

    print("\n" + "=" * 70)
    print(f"✓ Merge complete: {len(merged_df)} courses in output")
    print("=" * 70)


if __name__ == "__main__":
    main()
