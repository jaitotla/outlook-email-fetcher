from openmailbot.agent.chat_pipeline import ChatWithThreadPipeline
import logging
print("🔥 test.py file is executing 🔥")
print("📍 __file__ =", __file__)
logging.basicConfig(level=logging.INFO)

def test1():
    print("🚀 Starting test script")

    user_id = "user@example.com"
    thread_id = "19b3b6bd4843dd1d"
    question = "Summarize the main discussion points in this email thread"

    print("⚙️ Initializing pipeline")
    pipeline = ChatWithThreadPipeline()

    print("📥 Starting processing + chat")
    result = pipeline.process_and_chat(
        user_id=user_id,
        thread_id=thread_id,
        user_question=question
    )

    print("\n========= RESULT =========\n")
    print("Success:", result["success"])
    print("Answer:\n", result["answer"])
    print("\nProcessing Info:\n", result["processing_info"])


from openmailbot.agent.draft_pipeline import DraftWithAttachmentsPipeline

def main():
    print("🚀 Starting Draft Pipeline Test")

    user_id = "user@example.com"
    thread_id = "19b3b6bd4843dd1d"

    user_preferences = {
        "name": "Swapnil",
        "position": "AI Engineer",
        "tone": "professional and crisp",
        "custom_instructions": "Keep it short, direct, and business focused"
    }

    print("⚙️ Initializing Draft Pipeline")
    pipeline = DraftWithAttachmentsPipeline()

    print("📝 Running Draft Generation Pipeline")
    result = pipeline.process_email_request(
        user_id=user_id,
        thread_id=thread_id,
        user_preferences=user_preferences
    )

    print("\n========= DRAFT RESULT =========\n")
    print("Success:", result["success"])

    if result["success"]:
        print("\nGenerated Draft:\n")
        print(result["draft_content"])
    else:
        print("\nError:", result.get("error"))

    print("\nProcessing Info:\n", result["processing_info"])





if __name__ == "__main__":
    main()
