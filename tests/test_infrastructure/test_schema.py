from src.schema.models import AnalysisSchema, Dimension, FieldDef, SourcePrefs


def test_analysis_schema_defaults():
    schema = AnalysisSchema()
    assert schema.industry == "saas"
    assert schema.targets == []
    assert schema.dimensions == []
    assert schema.report_audience == "product_manager"
    assert schema.output_formats == ["markdown"]


def test_analysis_schema_with_dimensions():
    dim = Dimension(name="test_dim", agent_type="TestAgent", weight=2.0,
                    focus_points=["point1", "point2"], node_types=["FeatureNode"])
    schema = AnalysisSchema(dimensions=[dim], targets=["Notion", "Linear"])
    assert len(schema.dimensions) == 1
    assert schema.dimensions[0].name == "test_dim"
    assert schema.dimensions[0].weight == 2.0
    assert len(schema.dimensions[0].focus_points) == 2
    assert len(schema.targets) == 2


def test_dimension_defaults():
    dim = Dimension(name="d", agent_type="A")
    assert dim.description == ""
    assert dim.focus_points == []
    assert dim.node_types == []
    assert dim.prompt_override is None
    assert dim.weight == 1.0


def test_field_def_creation():
    fd = FieldDef(name="ai_score", type="float", description="AI maturity score",
                  range=(0, 10))
    assert fd.name == "ai_score"
    assert fd.type == "float"
    assert fd.range == (0, 10)
    assert fd.enum_values is None


def test_field_def_enum_type():
    fd = FieldDef(name="maturity", type="enum",
                  enum_values=["experimental", "beta", "ga"],
                  description="AI feature maturity level")
    assert fd.enum_values == ["experimental", "beta", "ga"]


def test_source_prefs_defaults():
    sp = SourcePrefs()
    assert sp.priority_sources == []
    assert sp.excluded_sources == []
    assert sp.min_credibility == 0.5
    assert sp.collection_depth == "standard"


def test_source_prefs_custom():
    sp = SourcePrefs(priority_sources=["G2", "ProductHunt"],
                     excluded_sources=["Reddit"],
                     min_credibility=0.7,
                     collection_depth="deep")
    assert "G2" in sp.priority_sources
    assert "Reddit" in sp.excluded_sources
    assert sp.min_credibility == 0.7
    assert sp.collection_depth == "deep"


def test_complex_schema():
    schema = AnalysisSchema(
        industry="saas",
        targets=["Notion", "Confluence", "Linear"],
        dimensions=[
            Dimension(name="定价分析", agent_type="PricingAnalyst", weight=0.4,
                      focus_points=["免费版限制", "升级路径"]),
            Dimension(name="AI能力", agent_type="FeatureAnalyzer", weight=0.6,
                      focus_points=["AI功能成熟度", "自研vs第三方"]),
        ],
        exclude_dimensions=["技术栈推断", "市场定位"],
        custom_fields={"FeatureNode": [
            FieldDef(name="ai_maturity", type="enum",
                     enum_values=["experimental", "beta", "ga"]),
        ]},
        dimension_weights={"定价分析": 0.4, "AI能力": 0.6},
        source_preferences=SourcePrefs(priority_sources=["G2"], min_credibility=0.6),
        benchmark_product="Notion",
        report_audience="product_manager",
    )
    assert len(schema.dimensions) == 2
    assert len(schema.exclude_dimensions) == 2
    assert schema.custom_fields["FeatureNode"][0].name == "ai_maturity"
    assert schema.benchmark_product == "Notion"
