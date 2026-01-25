from pydantic import BaseModel, Field, create_model


def system_field(default=..., **kwargs):
    """Mark a field as system-managed (LLM cannot see or modify)"""
    return Field(default, json_schema_extra={'llm_managed': False}, **kwargs)

def llm_field(default=..., **kwargs):
    """Mark a field as LLM-managed (LLM can see and modify)"""
    return Field(default, json_schema_extra={'llm_managed': True}, **kwargs)

class LLMManagedModel(BaseModel):
    """Base model with LLM visibility control"""

    @classmethod
    def for_llm_output(cls):
        """
        Create a version of this model for structured output with only LLM-managed fields.
        System-managed fields are excluded from the schema the LLM sees.

        Usage:
            TaskUpdateLLM = SearchTask.for_llm_output()
            llm.with_structured_output(TaskUpdateLLM)
        """
        fields = {}
        for field_name, field_info in cls.model_fields.items():
            extra = field_info.json_schema_extra or {}
            if extra.get('llm_managed', False):
                fields[field_name] = (field_info.annotation, field_info)

        return create_model(f"{cls.__name__}LLM", **fields, __base__=BaseModel)

    @classmethod
    def from_llm_output(cls, llm_data: BaseModel, existing_instance: 'LLMManagedModel'):
        """
        Merge LLM output back into full model instance.
        Only updates LLM-managed fields, preserves system-managed fields.
        """
        updated = existing_instance.model_copy(deep=True)

        for field_name, field_info in cls.model_fields.items():
            extra = field_info.json_schema_extra or {}
            if extra.get('llm_managed', False):
                if hasattr(llm_data, field_name):
                    setattr(updated, field_name, getattr(llm_data, field_name))

        return updated