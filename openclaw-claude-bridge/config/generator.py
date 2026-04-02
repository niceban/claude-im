"""Generate OpenClaw models.providers configuration fragment."""
import json
import os


def generate_provider_config(
    bridge_host: str = "127.0.0.1",
    bridge_port: int = 18792,
    provider_name: str = "claude-bridge",
    models: list = None
) -> dict:
    """Generate OpenClaw models.providers configuration fragment.

    Args:
        bridge_host: Host where bridge is running
        bridge_port: Port where bridge is running
        provider_name: Name for this provider
        models: List of model configs

    Returns:
        dict: Configuration fragment for openclaw.json
    """
    if models is None:
        models = [
            {"id": "claude-sonnet-4-6", "contextWindow": 200000},
            {"id": "claude-opus-4-6", "contextWindow": 200000},
            {"id": "claude-haiku-4-5", "contextWindow": 200000},
        ]

    config = {
        provider_name: {
            "provider": provider_name,
            "baseUrl": f"http://{bridge_host}:{bridge_port}",
            "api": "openai-completions",
            "models": {
                "defaults": [{"model": m["id"]} for m in models],
                "items": [
                    {
                        "id": m["id"],
                        "contextWindow": m.get("contextWindow", 200000)
                    }
                    for m in models
                ]
            }
        }
    }

    return config


def generate_openclaw_json_patch(
    provider_name: str = "claude-bridge",
    primary_model: str = "claude-sonnet-4-6",
    bridge_host: str = "127.0.0.1",
    bridge_port: int = 18792
) -> dict:
    """Generate complete patch for openclaw.json.

    Returns configuration to add to models.providers section.
    """
    provider_config = generate_provider_config(
        bridge_host=bridge_host,
        bridge_port=bridge_port,
        provider_name=provider_name
    )

    return provider_config


def main():
    """Generate and print configuration fragment."""
    config = generate_openclaw_json_patch()

    print("# Add this to ~/.openclaw/openclaw.json")
    print("# Under models.providers section:\n")
    print(json.dumps(config, indent=2))

    print("\n# Example complete configuration:")
    print("""
{
  "models": {
    "providers": {
      "claude-bridge": {
        "provider": "claude-bridge",
        "baseUrl": "http://127.0.0.1:18792",
        "api": "openai-completions",
        "models": {
          "defaults": [{"model": "claude-sonnet-4-6"}],
          "items": [
            {"id": "claude-sonnet-4-6", "contextWindow": 200000}
          ]
        }
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "claude-bridge/claude-sonnet-4-6"
      }
    }
  }
}
""")


if __name__ == "__main__":
    main()
