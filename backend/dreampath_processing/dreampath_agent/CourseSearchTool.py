from typing import List, Dict, Any, Optional
import weaviate
from weaviate.classes.query import Filter, Sort

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
                f3 = Filter.by_property("num_prereqs").less_than_or_equal(num_prereqs_max)
                flt = f3 if flt is None else (flt & f3)
            if course_code:
                f4 = Filter.by_property("course_code").equal(course_code)
                flt = f4 if flt is None else (flt & f4)
            return flt

    def hybrid_search(self, query: str, dept: Optional[str] = None, num_prereqs_max: Optional[int] = None, course_code: Optional[str] = None, sort_by_level: bool = False, limit: int = 10, alpha: float = 0.5):
        return_props = ["dept", "course_code", "course_title", "description", "prerequisites", "corequisites", "credits", "department", "level", "semester", "year", "url"]

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
        sort = []
        if sort_by_level:
            sort.append(Sort.by_property("level", ascending=True))

        kwargs = dict(
            query=query,
            alpha=alpha,
            filters=flt,
            limit=limit,
            return_properties=return_props,
        )

        if sort:
            kwargs["sort"] = sort

        res = self.collection.query.hybrid(**kwargs)
        return [o.properties for o in res.objects]