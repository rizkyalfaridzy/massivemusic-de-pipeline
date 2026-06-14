{# Use the +schema config value as the literal schema name (no target prefix),
   so models land in `staging` and `marts` rather than `analytics_staging`. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
