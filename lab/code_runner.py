"""Run student code in an isolated, resource-limited Docker container."""
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

from ai.tutor_engine import ai_tutor


class CodeRunnerEngine:
    IMAGE = "edupilot-runner:latest"
    MAX_CODE_CHARS = 100_000
    MAX_OUTPUT_CHARS = 500_000

    def execute(self, language: str, code_text: str, timeout_sec: int = 5) -> dict:
        lang = language.lower().strip()
        timeout_sec = max(1, min(int(timeout_sec), 10))
        if not code_text.strip():
            return {"status": "error", "output": "Enter a program before running it.", "ai_explanation": ""}
        if len(code_text) > self.MAX_CODE_CHARS:
            return {"status": "error", "output": "Program exceeds the 100,000 character limit.", "ai_explanation": ""}
        docker = shutil.which("docker")
        if not docker:
            return {"status": "unavailable", "output": "The isolated runner is not configured. Install Docker and build the edupilot-runner image; this program was not executed.", "ai_explanation": ""}
        if lang in ("python", "py"):
            source, commands = "solution.py", [["python", "/workspace/solution.py"]]
            display_lang = "Python"
        elif lang == "c":
            source, commands = "program.c", [["gcc", "/workspace/program.c", "-o", "/workspace/program"], ["/workspace/program"]]
            display_lang = "C"
        elif lang in ("c++", "cpp"):
            source, commands = "program.cpp", [["g++", "/workspace/program.cpp", "-o", "/workspace/program"], ["/workspace/program"]]
            display_lang = "C++"
        elif lang == "java":
            source, commands = "Main.java", [["javac", "/workspace/Main.java"], ["java", "-cp", "/workspace", "Main"]]
            display_lang = "Java"
        else:
            return {"status": "error", "output": f"Unsupported language: {language}", "ai_explanation": ""}

        with tempfile.TemporaryDirectory(prefix="edupilot-run-") as work_dir:
            try:
                os.chmod(work_dir, 0o777)
            except OSError:
                pass
            source_path = os.path.join(work_dir, source)
            with open(source_path, "w", encoding="utf-8") as stream:
                stream.write(code_text)
            try:
                os.chmod(source_path, 0o666)
            except OSError:
                pass
            try:
                results = []
                for command in commands:
                    result = self._run_container(docker, work_dir, command, timeout_sec)
                    results.append(result)
                    if result.returncode:
                        return self._format_result(display_lang, result.stdout, result.stderr,
                                                   result.returncode, code_text)
                result = results[-1]
                return self._format_result(display_lang, result.stdout, result.stderr,
                                           result.returncode, code_text)
            except subprocess.TimeoutExpired:
                return {"status": "timeout", "output": f"Execution exceeded the {timeout_sec}-second limit.",
                        "ai_explanation": "The sandbox stopped the program when its time limit expired."}
            except FileNotFoundError:
                return {"status": "unavailable", "output": "Docker is installed but could not start the isolated runner. Confirm the Docker service is running and build the edupilot-runner image.", "ai_explanation": ""}
            except subprocess.CalledProcessError as error:
                return {"status": "error", "output": (error.stderr or error.stdout or str(error))[:self.MAX_OUTPUT_CHARS], "ai_explanation": ""}
            except Exception as error:
                return {"status": "error", "output": str(error), "ai_explanation": ""}

    def _run_container(self, docker: str, work_dir: str, command: list[str], timeout_sec: int):
        container_name = f"edupilot-run-{uuid.uuid4().hex[:12]}"
        mount = f"type=bind,source={os.path.abspath(work_dir)},target=/workspace"
        args = [docker, "run", "--rm", "--pull=never", "--name", container_name,
                "--network=none", "--memory=256m", "--memory-swap=256m", "--cpus=1",
                "--pids-limit=64", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
                "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=10001:10001",
                "--mount", mount, "--workdir=/workspace", self.IMAGE, *command]
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=timeout_sec,
                                    stdin=subprocess.DEVNULL, shell=False)
        except subprocess.TimeoutExpired:
            subprocess.run([docker, "rm", "--force", container_name], capture_output=True,
                           timeout=4, shell=False)
            raise
        result.stdout = result.stdout[-self.MAX_OUTPUT_CHARS:]
        result.stderr = result.stderr[-self.MAX_OUTPUT_CHARS:]
        return result

    def _format_result(self, language: str, stdout: str, stderr: str, returncode: int, code: str) -> dict:
        failed = returncode != 0
        explanation = ai_tutor.explain_code_error(language, stderr, code) if failed else ""
        output = stdout if not stderr else f"{stdout}\n[Error Output]:\n{stderr}"
        return {"status": "error" if failed else "success",
                "output": output.strip() or "Program executed with no console output.",
                "ai_explanation": explanation}


code_runner = CodeRunnerEngine()
