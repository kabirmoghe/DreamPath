from typing import List, Dict, Any, Optional
import weaviate
from weaviate.classes.query import Filter, Sort
from dreampath_processing.dreampath_agent.types import CourseSearchOutput, CourseSearchResult, CourseSearchParams

class CourseSearchTool():
    def __init__(self, http_host="localhost", http_port=8080, http_secure=False, grpc_host="localhost", grpc_port=50051, grpc_secure=False, collection="Course"):
        self.client = weaviate.connect_to_custom(
            http_host=http_host,
            http_port=http_port,
            http_secure=http_secure,
            grpc_host=grpc_host,
            grpc_port=grpc_port,
            grpc_secure=grpc_secure,
        )
        self.collection = self.client.collections.get(collection)

    def close(self):
        self.client.close()

    def _build_filters(self, dept: Optional[str], num_prereqs_max: Optional[int], course_code: Optional[str] = None):
            flt = None
            if dept:
                flt = Filter.by_property("dept").equal(dept)
            if num_prereqs_max is not None:
                f3 = Filter.by_property("num_prereqs").less_or_equal(num_prereqs_max)
                flt = f3 if flt is None else (flt & f3)
            if course_code:
                f4 = Filter.by_property("course_code").equal(course_code)
                flt = f4 if flt is None else (flt & f4)
            return flt

    def hybrid_search(self, query: Optional[str] = None, dept: Optional[str] = None, num_prereqs_max: Optional[int] = None, course_code: Optional[str] = None, sort_by_level: bool = False, limit: int = 5, alpha: float = 0.5):
        return_props = ["dept", "course_code", "course_title", "description", "prerequisites", "level", "course_url"]

        flt = self._build_filters(
            dept=dept,
            num_prereqs_max=num_prereqs_max,
            course_code=course_code,
        )

        # 1) Exact lookup path: if a course_code is provided, we can skip vectors entirely
        if course_code and (not query or query.strip() == "" or alpha is None):
            res = self.collection.query.fetch_objects(
                filters=flt,
                limit=min(limit, 25),  # exact lookup rarely needs large limits
                return_properties=return_props,
            )
            return [o.properties for o in res.objects]
        
        # 2) Hybrid path (semantic + keyword)
        # Note: Sorting is not directly supported in hybrid queries in current Weaviate v4 client
        # We'll perform the query and sort results post-query if needed
        kwargs = dict(
            query=query if query else "",
            alpha=alpha,
            filters=flt,
            limit=limit,
            return_properties=return_props,
        )

        res = self.collection.query.hybrid(**kwargs)
        
        # Post-query sorting if requested
        if sort_by_level:
            # Sort results by level after retrieval
            sorted_objects = sorted(res.objects, key=lambda x: x.properties.get("level", float('inf')))
            # Create a new result object with sorted objects
            class SortedResult:
                def __init__(self, objects):
                    self.objects = objects
            res = SortedResult(sorted_objects)
        return [o.properties for o in res.objects]
    
    def structured_hybrid_search(self, params: CourseSearchParams) -> CourseSearchOutput:
        raw_results = self.hybrid_search(params.query, params.dept, params.num_prereqs_max, params.course_code, params.sort_by_level, params.limit, params.alpha)
        results = [CourseSearchResult(dept=result['dept'], course_code=result['course_code'], course_title=result['course_title'], description=result['description'], prerequisites=result['prerequisites'], course_url=result['course_url']) for result in raw_results]
        return CourseSearchOutput(results=results)

if __name__ == "__main__":
    tool = CourseSearchTool()
    
    try:
    #     ex_1 = tool.hybrid_search(query="machine learning", dept="COSC", num_prereqs_max=0, limit=5, alpha=0.5, sort_by_level=True)
    #     print(ex_1)

        params = CourseSearchParams(query="intro economics", dept="ECON", limit=5, alpha=0.5, sort_by_level=True)
        ex_2 = tool.structured_hybrid_search(params)
        print(ex_2)
    finally:
        tool.close()