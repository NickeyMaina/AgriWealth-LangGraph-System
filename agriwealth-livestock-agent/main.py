import logging
from typing import Optional, Dict, Any
from agriwealth_agent import app
from state import AgentState

# -----------------------
# Logging Configuration
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AgriWealthMain")

# -----------------------
# High-level query processor
# -----------------------
def process_livestock_query(question: str, current_mode: Optional[str] = None) -> Dict[str, Any]:
    """
    Wrapper to run the compiled workflow for a user's livestock query.
    Initializes a clean state for each turn to prevent infinite recursion.
    Returns: type, message, next_mode, final_state
    """
    try:
        # FIX: Always initialize a CLEAN state for the new turn.
        state = AgentState(
            question=question,
            mode=current_mode, # Pass the mode directly
            db_entry="",
            sql_query=[],
            query_result="",
            query_rows={},
            attempts=0,
            relevance="",
            sql_error=False,
            animal_type="unknown",
            intent=""
        )

        # Run workflow
        final_state = app.invoke(state) 

        if "query_result" in final_state:
            return {
                "type": "success",
                "message": final_state["query_result"],
                "next_mode": final_state.get("mode", current_mode),
                "final_state": final_state
            }
        else:
            return {
                "type": "error",
                "message": "Workflow completed but no result was generated. Check agent logs for details.",
                "next_mode": current_mode,
                "final_state": final_state
            }

    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        return {
            "type": "error",
            "message": f"Internal error in the LangGraph workflow: {str(e)}",
            "next_mode": current_mode,
            "final_state": {}
        }


# -----------------------
# CLI Interface for Testing
# -----------------------
def main():
    print("Welcome to AgriWealth Livestock Assistant! (Conversational Mode)")
    print("Type 'exit' or 'quit' to end the session.")
    
    current_mode = '1'
    
    # --- Initial Setup ---
    print("\n--- Initial Setup ---")
    print("Select Mode:")
    print("1 - Database Query (e.g., 'What is the oldest cow?')")
    print("2 - Disease Diagnosis (e.g., 'What is wrong with my chicken, it has ruffled feathers?')")
    print("3 - Web Research (e.g., 'How often should I deworm my goats?')")
    
    mode_input = input("Enter mode (1/2/3) or press Enter to use default '1': ").strip()
    if mode_input in ['1', '2', '3']:
        current_mode = mode_input
    elif mode_input:
        print("Invalid mode. Starting in Database Query (Mode 1).")
        
    print(f"Starting in Mode {current_mode}.")
    
    # --- Interactive Loop ---
    while True:
        try:
            print(f"\nMode: {current_mode} | Enter question (or '1'/'2'/'3' to change mode):")
                 
            question_input = input("> ").strip()
            
            if question_input.lower() in ['exit', 'quit']:
                print("\nThank you for using AgriWealth. Goodbye!")
                break
                
            if not question_input:
                continue

            # Check if the user wants to switch modes explicitly
            if question_input in ['1', '2', '3']:
                current_mode = question_input
                print(f"--- Mode switched to {current_mode} ---")
                continue

            # Process the query using a clean state initialized with the new input
            # FIX: We only need the question and current_mode for the next invocation.
            result = process_livestock_query(question_input, current_mode)

            print("\n--- Agent Response ---")
            print(result["message"])

            # Update current_mode in case the graph successfully transitioned modes internally (unlikely but safe)
            current_mode = result["next_mode"]
            
            if result["type"] == "error":
                print(f"\n[Error] The query failed in Mode {current_mode}. Try rephrasing.")
                
        except KeyboardInterrupt:
            print("\n\nSession interrupted by user. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Critical error in main loop: {e}")
            break


if __name__ == "__main__":
    main()
