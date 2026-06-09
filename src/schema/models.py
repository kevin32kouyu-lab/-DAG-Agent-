from pydantic import BaseModel, Field


class FieldDef(BaseModel):
    name: str
    type: str  # str, int, float, enum, bool
    description: str = ""
    enum_values: list[str] | None = None
    range: tuple[float, float] | None = None


class Dimension(BaseModel):
    name: str
    description: str = ""
    focus_points: list[str] = Field(default_factory=list)
    node_types: list[str] = Field(default_factory=list)
    agent_type: str = ""
    prompt_override: str | None = None
    weight: float = 1.0


class SourcePrefs(BaseModel):
    priority_sources: list[str] = Field(default_factory=list)
    excluded_sources: list[str] = Field(default_factory=list)
    min_credibility: float = 0.5
    collection_depth: str = "standard"


class AnalysisSchema(BaseModel):
    industry: str = "saas"
    targets: list[str] = Field(default_factory=list)
    dimensions: list[Dimension] = Field(default_factory=list)
    exclude_dimensions: list[str] = Field(default_factory=list)
    custom_fields: dict[str, list[FieldDef]] = Field(default_factory=dict)
    dimension_weights: dict[str, float] = Field(default_factory=dict)
    source_preferences: SourcePrefs = Field(default_factory=SourcePrefs)
    benchmark_product: str | None = None
    report_audience: str = "product_manager"
    report_sections: list[str] = Field(default_factory=list)
    output_formats: list[str] = Field(default_factory=lambda: ["markdown"])
