import weaviate
import threading
from typing import Optional, Dict, Any
from weaviate.classes.query import Filter
import json
import os
import warnings
from dreampath_processing.courses.data_retrieval.college_info_retrieval import DATA_DIR

# Suppress ResourceWarnings from Weaviate - singleton pattern keeps connections open intentionally
warnings.filterwarnings('ignore', category=ResourceWarning, message='unclosed')

class WeaviateCourseService:
    """
    Service for efficient course data retrieval using Weaviate vector database.
    Thread-safe and designed for production use across multiple application components.
    """

    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, http_host="localhost", http_port=8080, http_secure=False, 
                grpc_host="localhost", grpc_port=50051, grpc_secure=False):
        if cls._instance is None:
            print("Creating new WeaviateCourseService instance")
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, http_host=None, http_port=None, http_secure=None,
                 grpc_host=None, grpc_port=None, grpc_secure=None):
        if not self._initialized:
            # Use environment variables with fallbacks to defaults
            http_host = http_host or os.getenv("WEAVIATE_HTTP_HOST", "localhost")
            http_port = http_port or int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
            http_secure = http_secure if http_secure is not None else os.getenv("WEAVIATE_HTTP_SECURE", "false").lower() == "true"
            grpc_host = grpc_host or os.getenv("WEAVIATE_GRPC_HOST", "localhost")
            grpc_port = grpc_port or int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
            grpc_secure = grpc_secure if grpc_secure is not None else os.getenv("WEAVIATE_GRPC_SECURE", "false").lower() == "true"

            self.client = weaviate.connect_to_custom(
                http_host=http_host,
                http_port=http_port,
                http_secure=http_secure,
                grpc_host=grpc_host,
                grpc_port=grpc_port,
                grpc_secure=grpc_secure,
                skip_init_checks=True,  # Skip gRPC health check for cloud deployments
                headers={"X-OpenAI-Api-Key": os.getenv("OPENAI_API_KEY", "")},
            )

            self.course_collection = self.client.collections.get("Course")
            self.major_collection = self.client.collections.get("Major")
            self._initialized = True
            with open(f"{DATA_DIR}/undergrad_department_ids.json", 'r') as f:
                self.department_ids = json.load(f)
    
    def get_course_by_code(self, course_code: str) -> Optional[Dict[str, Any]]:
        """
        Get course information by course code from Weaviate.
        Returns None if course not found.
        
        Args:
            course_code: The course code to look up (e.g., "COSC55")
            
        Returns:
            Dictionary with course properties or None
        """
        try:
            # Use Weaviate filter to find exact course code match
            result = self.course_collection.query.fetch_objects(
                filters=Filter.by_property("course_code").equal(course_code),
                limit=1,
                return_properties=[
                    "course_code", "department_id", "department", "course_title", "description",
                    "prerequisites", "best_prereq_path", "num_prereqs",
                    "level", "degree_req", "course_url", "course_id",
                    "total_reviews",
                    "global_difficulty_percentile", "global_difficulty_classification",
                    "dept_difficulty_percentile", "dept_difficulty_classification", "difficulty_blurb",
                    "global_value_percentile", "global_value_classification",
                    "dept_value_percentile", "dept_value_classification",
                    "learning_value_blurb", "target_audience_blurb"
                ]
            )
            
            if result.objects:
                return result.objects[0].properties
            return None
            
        except Exception as e:
            print(f"Error retrieving course {course_code}: {e}")
            return None
        
    def course_code_exists(self, course_code: str) -> bool:
        """
        Check if a course code exists in Weaviate.
        """
        try:
            result = self.course_collection.query.fetch_objects(
                filters=Filter.by_property("course_code").equal(course_code),
                limit=1,
            )
            return len(result.objects) > 0
        except Exception as e:
            print(f"Error checking if course {course_code} exists: {e}")
            return False
    
    def is_major_course(self, course_code: str, major: str) -> bool:
        """
        Check if a course code is a major course.
        """
        # Get major department id
        major_data = self.get_major_info(major)
        major_department_id = major_data['department_id']

        # Get course department id
        course_data = self.get_course_by_code(course_code)
        course_department_id = course_data['department_id']
        return major_department_id == course_department_id

    def get_major_info(self, major: str) -> Optional[Dict[str, Any]]:
        """
        Get major information.
        """
        major_data = self.major_collection.query.fetch_objects(
            filters=Filter.by_property("major").equal(major),
            limit=1,
        )
            
        if len(major_data.objects) == 0:
            return None
            
        return major_data.objects[0].properties
    
    def _build_filters(self, department: Optional[str]=None, course_code: Optional[str]=None, max_num_prereqs: Optional[int]=None, difficulty_classification: Optional[str]=None, value_classification: Optional[str]=None):
        """
        Build Weaviate filters based on search parameters.
        
        Args:
            department: Department name (e.g., "Computer Science")
            course_code: Specific course code to filter by
            max_num_prereqs: Maximum number of prerequisites
            difficulty_classification: Difficulty classification (e.g., "Low", "Medium", "High")
            value_classification: Value classification (e.g., "High", "Medium", "Low")
            
        Returns:
            Weaviate Filter object or None
        """
        from weaviate.classes.query import Filter
        
        filters = None
        
        if department:
            # Use department_id for filtering if we have the mapping
            department_id = self.department_ids.get(department)
            if department_id:
                filters = Filter.by_property("department_id").equal(department_id)
            else:
                raise ValueError(f"Invalid department: {department}")
                
        if course_code:
            code_filter = Filter.by_property("course_code").equal(course_code)
            filters = code_filter if filters is None else (filters & code_filter)

        if max_num_prereqs is not None:
            prereq_filter = Filter.by_property("num_prereqs").less_or_equal(max_num_prereqs)
            filters = prereq_filter if filters is None else (filters & prereq_filter)
            
        if difficulty_classification:
            difficulty_filter = Filter.by_property("global_difficulty_classification").equal(difficulty_classification)
            filters = difficulty_filter if filters is None else (filters & difficulty_filter)

        if value_classification:
            value_filter = Filter.by_property("global_value_classification").equal(value_classification)
            filters = value_filter if filters is None else (filters & value_filter)

        return filters
    
    def close(self):
        """Close the Weaviate connection"""
        if hasattr(self, 'client'):
            self.client.close()
    
    def __del__(self):
        """Ensure connection is closed when service is destroyed"""
        try:
            self.close()
        except:
            pass

# Global instance accessor
def  get_weaviate_course_service() -> WeaviateCourseService:
    """Get the singleton WeaviateCourseService instance"""
    return WeaviateCourseService() 