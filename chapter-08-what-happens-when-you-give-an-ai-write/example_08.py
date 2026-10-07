def safe_tool_call(tool_func, fallback_value=None, required=False):
    """Execute a tool call with failure handling."""
    try:
        result = tool_func()
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        logger.error(f"Tool call failed: {tool_func.__name__}", exc_info=True)

        if required:
            raise  # Fail fast if this tool is critical

        return {
            'success': False,
            'data': fallback_value,
            'error': str(e),
            'tool': tool_func.__name__
        }

# Usage in investigation flow
metrics_result = safe_tool_call(
    lambda: get_cloudwatch_metrics(...),
    fallback_value={'note': 'Metrics unavailable during investigation'},
    required=False
)

source_result = safe_tool_call(
    lambda: read_source_files(affected_files),
    fallback_value={},
    required=True  # Cannot proceed without source code
)
