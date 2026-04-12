from langchain_openai import ChatOpenAI

def get_llm(model="gpt-5-nano", temperature=0):
    return ChatOpenAI(model=model, temperature=temperature)
