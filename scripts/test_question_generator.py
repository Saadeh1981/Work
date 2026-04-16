from backend.services.question_generator import generate_questions


def main():
    sample = [
        {
            "snippet": "Plant Capacity 120 MW",
            "confidence": 0.9,
        },
        {
            "snippet": "Capacity maybe 12 MW",
            "confidence": 0.55,
        },
    ]

    questions = generate_questions(sample)

    print("Questions:")
    for q in questions:
        print(q)


if __name__ == "__main__":
    main()