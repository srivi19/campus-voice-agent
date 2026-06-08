"""
chat.py
Simple terminal chat interface for CampusVoice.
"""

from agent_mcp import ask

BANNER = """
╔══════════════════════════════════════════════════════════╗
║           🎓 CampusVoice — Student Review Agent          ║
║   Powered by Gemini + Elasticsearch                      ║
╚══════════════════════════════════════════════════════════╝

Schools available: UTK (utk) | Vanderbilt (vanderbilt) | Both (leave blank)

Commands:
  school utk          → filter to UTK only
  school vanderbilt   → filter to Vanderbilt only
  school all          → search both schools
  quit                → exit

"""

def main():
    print(BANNER)
    school_filter = None
    current_school = "both schools"

    while True:
        try:
            user_input = input(f"[{current_school}] Ask > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            print("Goodbye!")
            break

        if user_input.lower().startswith("school "):
            arg = user_input.split(" ", 1)[1].strip().lower()
            if arg == "utk":
                school_filter = "utk"
                current_school = "UTK"
            elif arg in ("vanderbilt", "vandy"):
                school_filter = "vanderbilt"
                current_school = "Vanderbilt"
            elif arg == "all":
                school_filter = None
                current_school = "both schools"
            else:
                print("Unknown school. Use: utk, vanderbilt, or all")
            continue

        print("\n🔍 Searching reviews...\n")
        try:
            # school filter is embedded in the question for MCP agent
            q = user_input
            if school_filter:
                q = f"[Filter to {school_filter} only] {user_input}"
            answer = ask(q)
            print(f"📊 {answer}\n")
            print("-" * 60)
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
