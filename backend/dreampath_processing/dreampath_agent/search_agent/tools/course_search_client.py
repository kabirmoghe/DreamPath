from typing import Any

from dreampath_processing.dreampath_agent.search_agent.types.course_types import (
    CourseSearchOutput,
    CourseSearchParams,
    CourseSearchResult,
)
from dreampath_processing.weaviate.course_service import (
    get_weaviate_course_service,
)


class CourseSearchClient:
    """
    Course search client that uses the WeaviateCourseService for efficient course lookups.
    This approach reuses the singleton service connection instead of creating new connections.
    """
    
    def __init__(self):
        # Use the singleton service instead of creating our own connection
        self.service = get_weaviate_course_service()
    
    def close(self):
        """Close connection - delegates to the service"""
        # Note: Since we're using a singleton, we don't actually close the connection
        # as other components might still be using it. The service manages its own lifecycle.
        pass

    def hybrid_search(self, query: str | None = None, alpha: float | None = None, department: str | None = None, course_code: str | None = None,
                     max_num_prereqs: int | None = None, difficulty_classification: str | None = None, value_classification: str | None = None, 
                     sort_by_level: bool = False, limit: int = 5) -> list[dict[str, Any]]:
        """
        Perform hybrid search using the WeaviateCourseService.
        
        Args:
            query: Search query string
            alpha: Hybrid search balance (0=keyword, 1=vector)
            department: Department filter (e.g., "COSC", "MATH")
            course_code: Specific course code to search for
            max_num_prereqs: Maximum number of prerequisites
            difficulty_classification: Difficulty classification (e.g., "Low", "Medium", "High")
            value_classification: Value classification (e.g., "High", "Medium", "Low")
            sort_by_level: Whether to sort results by course level
            limit: Maximum number of results to return
            
        Returns:
            List of course dictionaries matching the search criteria
        """
        # The WeaviateCourseService doesn't have hybrid_search method yet, so let's use the existing logic
        # but delegate the Weaviate operations to the service
        return_props = ["department", 
        "course_code", 
        "course_title", 
        "description", 
        "prerequisites", 
        "course_url",
        "num_prereqs",
        "total_reviews",
        "global_difficulty_percentile", 
        "global_difficulty_classification",
        "dept_difficulty_percentile",
        "dept_difficulty_classification",
        "difficulty_blurb",
        "global_value_percentile",
        "global_value_classification",
        "dept_value_percentile",
        "dept_value_classification",
        "learning_value_blurb",
        "target_audience_blurb"]

        # Build filters using the service's method
        flt = self.service._build_filters(department=department, course_code=course_code, max_num_prereqs=max_num_prereqs, difficulty_classification=difficulty_classification, value_classification=value_classification)

        # 1) Exact lookup path: if a course_code is provided, we can skip vectors entirely
        # Use exact lookup when: course_code is set AND (no query OR alpha is 0/None)
        if course_code and (not query or query.strip() == "" or alpha is None or alpha == 0):
            res = self.service.course_collection.query.fetch_objects(
                filters=flt,
                limit=min(limit, 25),  # exact lookup rarely needs large limits
                return_properties=return_props,
            )
            results = [o.properties for o in res.objects]
        else:
            # 2) Hybrid path (semantic + keyword)
            kwargs = dict(
                query=query if query else "",
                alpha=alpha,
                filters=flt,
                limit=limit,
                return_properties=return_props,
            )

            res = self.service.course_collection.query.hybrid(**kwargs)
            results = [o.properties for o in res.objects]

        # Post-query sorting if requested
        if sort_by_level and results:
            results.sort(key=lambda x: x.get("level", float('inf')))

        return results
    
    def structured_hybrid_search(self, params: CourseSearchParams) -> CourseSearchOutput:
        """
        Perform structured hybrid search using CourseSearchParams.
        
        Args:
            params: CourseSearchParams object with search parameters
            
        Returns:
            CourseSearchOutput with structured results
        """

        # print(f"Structured hybrid search with params: {params}")

        raw_results = self.hybrid_search(
            query=params.query,
            alpha=params.alpha,
            department=params.department,
            course_code=params.course_code,
            max_num_prereqs=params.max_num_prereqs,
            difficulty_classification=params.difficulty_classification,
            value_classification=params.value_classification,
            sort_by_level=params.sort_by_level,
            limit=params.limit,
        )
        
        results = []
        for result in raw_results:
            try:
                course_result = CourseSearchResult(
                    course_code=result.get('course_code', ''),
                    department=result.get('department', ''),
                    course_title=result.get('course_title', ''),
                    description=result.get('description', ''),
                    prerequisites=result.get('prerequisites', ''),
                    course_url=result.get('course_url', ''),
                    num_prereqs=result.get('num_prereqs', 0),
                    total_reviews=result.get('total_reviews', 0),
                    global_difficulty_percentile=result.get('global_difficulty_percentile', ''),
                    global_difficulty_classification=result.get('global_difficulty_classification', ''),
                    dept_difficulty_percentile=result.get('dept_difficulty_percentile', ''),
                    dept_difficulty_classification=result.get('dept_difficulty_classification', ''),
                    difficulty_blurb=result.get('difficulty_blurb', ''),
                    global_value_percentile=result.get('global_value_percentile', ''),
                    global_value_classification=result.get('global_value_classification', ''),
                    dept_value_percentile=result.get('dept_value_percentile', ''),
                    dept_value_classification=result.get('dept_value_classification', ''),
                    learning_value_blurb=result.get('learning_value_blurb', ''),
                    target_audience_blurb=result.get('target_audience_blurb', '')
                )
                results.append(course_result)
            except Exception as e:
                print(f"Error creating CourseSearchResult: {e}")
                continue
        
        return CourseSearchOutput(results=results)
 
    def structured_get_course_by_code(self, course_code: str) -> CourseSearchResult | None:
        """
        Get a specific course by its code.
        
        Args:
            course_code: The course code to look up
            
        Returns:
            Course dictionary or None if not found
        """
        result = self.service.get_course_by_code(course_code)

        print(f"Result: {result}")

        if result:
            return CourseSearchResult(
                course_code=result.get('course_code', ''),
                department=result.get('department', ''),
                course_title=result.get('course_title', ''),
                description=result.get('description', ''),
                prerequisites=result.get('prerequisites', ''),
                course_url=result.get('course_url', ''))
        else:
            return None

if __name__ == "__main__":
    tool = CourseSearchClient()
    
    try:
        # Test basic hybrid search
        print("Testing hybrid search...")
        results = tool.hybrid_search(query="machine learning", department="Computer Science", limit=3, alpha=0.5)
        print(f"Found {len(results)} results")
        for result in results[:2]:  # Show first 2
            print(f"  - {result.get('course_code')}: {result.get('course_title')}")
        
        # Test structured search
        print("\nTesting structured search...")
        params = CourseSearchParams(
            query="intro economics", 
            department="Economics", 
            limit=5, 
            alpha=0.5, 
            sort_by_level=True,
            num_prereqs_max=0
        )
        structured_results = tool.structured_hybrid_search(params)
        print(f"Structured search found {len(structured_results.results)} results")
        for result in structured_results.results[:2]:  # Show first 2
            print(f"  - {result.course_code}: {result.course_title}")
        
        # Test specific course lookup
        print("\nTesting course lookup...")
        course = tool.get_course_by_code("COSC55")
        if course:
            print(f"Found course: {course.get('course_code')} - {course.get('course_title')}")
        else:
            print("Course COSC55 not found")
            
    except Exception as e:
        print(f"Error in testing: {e}")
    finally:
        tool.close()