"""
AI Programming Tutor supporting Java, Python, C/C++, SQL, DBMS, OS, CN, OOP, Data Structures, Algorithms.
"""

TUTOR_KNOWLEDGE = {
    "java": {
        "title": "Java Programming",
        "concepts": "Object-Oriented Programming, JVM/JRE/JDK, Garbage Collection, Multithreading, Exception Handling, Collections Framework.",
        "example": "class HelloWorld {\n    public static void main(String[] args) {\n        System.out.println(\"Hello, VCET!\");\n    }\n}"
    },
    "python": {
        "title": "Python Programming",
        "concepts": "Dynamic Typing, List Comprehensions, Decorators, Generators, GIL, Asyncio, PySide6 GUI development.",
        "example": "def main():\n    students = [\"Arun\", \"Bala\", \"Dinesh\"]\n    print(f\"Enrolled students: {', '.join(students)}\")\n\nif __name__ == '__main__':\n    main()"
    },
    "c": {
        "title": "C & C++ Programming",
        "concepts": "Pointers, Memory Allocation (malloc/free), Structs, OOP in C++ (Classes, Inheritance, Polymorphism, Templates, STL).",
        "example": "#include <stdio.h>\nint main() {\n    printf(\"Welcome to C Lab!\\n\");\n    return 0;\n}"
    },
    "sql": {
        "title": "SQL & DBMS",
        "concepts": "DDL, DML, DCL, Joins, Indexing, Transactions, ACID Properties, Normalization (1NF to BCNF), Query Optimization.",
        "example": "SELECT st.name, COUNT(ar.id) AS attendance_count\nFROM students st\nJOIN attendance_records ar ON ar.student_id = st.id\nWHERE ar.status = 'Present'\nGROUP BY st.id, st.name;"
    },
    "dsa": {
        "title": "Data Structures & Algorithms",
        "concepts": "Arrays, Linked Lists, Stacks, Queues, Binary Trees, Graphs, Sorting (QuickSort, MergeSort), Dynamic Programming.",
        "example": "def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1"
    },
    "os": {
        "title": "Operating Systems",
        "concepts": "Process Scheduling (FCFS, SJF, Round Robin), Deadlock Prevention, Memory Management (Paging, Segmentation), Virtual Memory.",
        "example": "Semaphore mutex = 1;\nvoid process() {\n    wait(mutex);\n    // Critical Section\n    signal(mutex);\n}"
    },
    "cn": {
        "title": "Computer Networks",
        "concepts": "OSI 7 Layer Model, TCP vs UDP, IP Addressing & Subnetting, Routing Algorithms, HTTP/S, DNS, Socket Programming.",
        "example": "Client -> [TCP Handshake: SYN] -> Server\nServer -> [SYN-ACK] -> Client\nClient -> [ACK] -> Connection Established"
    }
}

class AIProgrammingTutor:
    """
    Offline Programming Tutor providing topic overviews, code samples, and concept explanations.
    """
    def get_topic_info(self, topic_key: str) -> dict:
        key = topic_key.lower().strip()
        for k, data in TUTOR_KNOWLEDGE.items():
            if k in key or data["title"].lower() in key:
                return data
        return TUTOR_KNOWLEDGE["python"]

    def explain_code_error(self, language: str, error_message: str, code: str) -> str:
        """Analyzes compilation/runtime errors and provides clear guidance."""
        err = error_message.lower()
        if "syntaxerror" in err or "expected" in err:
            return "Syntax Error Detected: Check missing colons, brackets, or semicolons in your code."
        elif "indentationerror" in err:
            return "Indentation Error: Ensure consistent use of 4 spaces for block indentation."
        elif "nameerror" in err or "cannot find symbol" in err:
            return "Name / Symbol Error: Variable or class name is not defined before use. Check spelling."
        elif "zerodivisionerror" in err or "by zero" in err:
            return "Division By Zero: Add a check to verify divisor is not 0 before division."
        elif "nullpointerexception" in err or "attributeerror" in err:
            return "Null Pointer / Attribute Error: Attempted to access property on null or undefined object."
        return f"Compiler Diagnostic ({language}):\nReview error output carefully on the indicated line number. Verify input parameters and variable types."

ai_tutor = AIProgrammingTutor()
