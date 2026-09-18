from app.graph import graph


def main():
    initial_state = {
        "message": "Hello LangGraph"
    }

    result = graph.invoke(initial_state)

    print("Graph result:")
    print(result)


if __name__ == "__main__":
    main()