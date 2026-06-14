{# Safely cast a value to integer, returning NULL on non-numeric input.
   Casts to text first so it works whether the source column is text or numeric. #}
{% macro try_cast_int(column) -%}
    case
        when ({{ column }})::text ~ '^-?[0-9]+$' then ({{ column }})::text::integer
        else null
    end
{%- endmacro %}
