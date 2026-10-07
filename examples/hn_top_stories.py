"""Example: extract top Hacker News stories."""
import asyncio
import os
from agent import BrowserAgent, AgentConfig

async def main():
    config = AgentConfig(
        api_key=os.environ["NVIDIA_API_KEY"],
        model="nvidia/nemotron-3-super-120b-a12b",
        headless=True,
        max_steps=12,
    )
    async with BrowserAgent(config) as agent:
        result = await agent.run_task(
            "Extract rank, title, and points for the top 5 Hacker News stories.",
            url="https://news.ycombinator.com",
            data_schema={
                "stories": [
                    {"rank": "integer", "title": "string", "points": "integer"}
                ]
            },
        )
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
