import os
import sys
import tempfile
import subprocess
from ai.tutor_engine import ai_tutor

class CodeRunnerEngine:
    """
    Executes Python, Java, C, and C++ source code in a sandboxed subprocess with execution timeout.
    """
    def execute(self, language: str, code_text: str, timeout_sec: int = 5) -> dict:
        lang = language.lower().strip()
        temp_dir = tempfile.mkdtemp()
        
        try:
            if lang == "python":
                file_path = os.path.join(temp_dir, "solution.py")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code_text)

                result = subprocess.run(
                    [sys.executable, file_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec
                )
                return self._format_result("Python", result.stdout, result.stderr, result.returncode, code_text)

            elif lang == "c":
                exe_name = "program.exe" if sys.platform == "win32" else "program"
                src_path = os.path.join(temp_dir, "program.c")
                exe_path = os.path.join(temp_dir, exe_name)
                with open(src_path, "w", encoding="utf-8") as f:
                    f.write(code_text)

                compile_res = subprocess.run(["gcc", src_path, "-o", exe_path], capture_output=True, text=True)
                if compile_res.returncode != 0:
                    return self._format_result("C (Compilation)", "", compile_res.stderr, compile_res.returncode, code_text)

                run_res = subprocess.run([exe_path], capture_output=True, text=True, timeout=timeout_sec)
                return self._format_result("C", run_res.stdout, run_res.stderr, run_res.returncode, code_text)

            elif lang == "c++" or lang == "cpp":
                exe_name = "program.exe" if sys.platform == "win32" else "program"
                src_path = os.path.join(temp_dir, "program.cpp")
                exe_path = os.path.join(temp_dir, exe_name)
                with open(src_path, "w", encoding="utf-8") as f:
                    f.write(code_text)

                compile_res = subprocess.run(["g++", src_path, "-o", exe_path], capture_output=True, text=True)
                if compile_res.returncode != 0:
                    return self._format_result("C++ (Compilation)", "", compile_res.stderr, compile_res.returncode, code_text)

                run_res = subprocess.run([exe_path], capture_output=True, text=True, timeout=timeout_sec)
                return self._format_result("C++", run_res.stdout, run_res.stderr, run_res.returncode, code_text)

            elif lang == "java":
                src_path = os.path.join(temp_dir, "Main.java")
                with open(src_path, "w", encoding="utf-8") as f:
                    f.write(code_text)

                compile_res = subprocess.run(["javac", src_path], capture_output=True, text=True)
                if compile_res.returncode != 0:
                    return self._format_result("Java (Compilation)", "", compile_res.stderr, compile_res.returncode, code_text)

                run_res = subprocess.run(["java", "-cp", temp_dir, "Main"], capture_output=True, text=True, timeout=timeout_sec)
                return self._format_result("Java", run_res.stdout, run_res.stderr, run_res.returncode, code_text)

            else:
                return {"status": "error", "output": f"Unsupported language: {language}", "ai_explanation": ""}

        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "output": "Execution timed out! Ensure there are no infinite loops or unresolved input prompts.",
                "ai_explanation": "Execution Time Exceeded (Limit 5s)."
            }
        except FileNotFoundError as fnf_err:
            missing_tool = fnf_err.filename or "Compiler/Runtime"
            return {
                "status": "error",
                "output": f"Compiler or Runtime binary '{missing_tool}' was not found in your system PATH.",
                "ai_explanation": f"Missing Toolchain: Please install {missing_tool} (e.g., GCC / MinGW / JDK / Python) and add it to your OS system PATH."
            }
        except Exception as e:
            return {
                "status": "error",
                "output": str(e),
                "ai_explanation": f"System execution error: {e}"
            }

    def _format_result(self, lang: str, stdout: str, stderr: str, returncode: int, code: str) -> dict:
        has_error = returncode != 0 or len(stderr.strip()) > 0
        ai_msg = ""
        if has_error:
            ai_msg = ai_tutor.explain_code_error(lang, stderr, code)
        
        output = stdout if not stderr else f"{stdout}\n[Error Output]:\n{stderr}"
        return {
            "status": "success" if not has_error else "error",
            "output": output.strip() if output.strip() else "Program executed with no console output.",
            "ai_explanation": ai_msg
        }

code_runner = CodeRunnerEngine()
