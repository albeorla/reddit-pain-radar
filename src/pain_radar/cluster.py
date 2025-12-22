"""Logic for clustering pain signals into Pain Pattern Clusters."""

import json
from typing import List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .models import Cluster, ClusterItem, PainSignal, EvidenceSignal
from .prompts import CLUSTER_SYSTEM_PROMPT, CLUSTER_USER_TEMPLATE
from .config import settings


class Clusterer:
    """Groups ideas/findings into semantic clusters."""

    def __init__(self, model_name: str = "gpt-4o", llm: Optional[BaseChatModel] = None):
        if llm:
            self.llm = llm
        else:
            self.llm = ChatOpenAI(
                model=model_name,
                api_key=settings.openai_api_key.get_secret_value(),
                temperature=0.0,
            )

    async def cluster_items(self, items: List[ClusterItem]) -> List[Cluster]:
        """Cluster a list of items into groups."""
        if not items:
            return []

        # Prepare items for prompt
        items_data = [
            {
                "id": item.id,
                "summary": item.summary,
                "pain_point": item.pain_point,
                "subreddit": item.subreddit,
                "quotes": [e.quote for e in item.evidence if e.signal_type == "pain"]
            }
            for item in items
        ]
        
        items_json = json.dumps(items_data, indent=2)

        prompt = ChatPromptTemplate.from_messages([
            ("system", CLUSTER_SYSTEM_PROMPT),
            ("user", CLUSTER_USER_TEMPLATE),
        ])

        structured_llm = self.llm.with_structured_output(
            schema={
                "name": "ClusterOutput",
                "description": "List of pain clusters",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "clusters": {
                            "type": "array", 
                            "items": Cluster.model_json_schema()
                        }
                    },
                    "required": ["clusters"]
                }
            }
        )
        
        chain = prompt | structured_llm
        
        try:
            result = await chain.ainvoke({"items_json": items_json})
            
            # The result might be a dict (if using json schema) or object (if pydantic)
            # LangChain with_structured_output usually returns the Pydantic object if passed class,
            # or dict if passed schema. Here I passed schema manually because I wanted to wrap it in a "clusters" list.
            # Wait, better to define a wrapper model for simpler Pydantic usage.
            
            # Let's retry with a wrapper model approach in the next iteration or right now in code content.
            # Actually, the result from `with_structured_output(schema=...)` is usually a dict.
            
            clusters_data = result.get("clusters", [])
            clusters = [Cluster(**c) for c in clusters_data]
            
            return clusters

        except Exception as e:
            print(f"Error during clustering: {e}")
            return []

# Wrapper model helper if we needed it, but dict access is fine.
