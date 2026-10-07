class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, name: str, func: callable, description: str, parameters: dict):
        self.tools[name] = {
            'function': func,
            'description': description,
            'parameters': parameters
        }

    def as_bedrock_schema(self) -> list:
        """Convert tools to Bedrock's tool schema format."""
        return [{
            'name': name,
            'description': tool['description'],
            'input_schema': {
                'type': 'object',
                'properties': tool['parameters'],
                'required': list(tool['parameters'].keys())
            }
        } for name, tool in self.tools.items()]
