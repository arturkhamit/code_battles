from infrastructure.sandbox.executor import run_in_docker


async def execute_and_test_code(task_data: dict, language: str, user_code: str) -> dict:
    stdin_data = []
    expected_outputs = []

    for test_group in ["public_tests", "generated_tests"]:
        if test_group in task_data:
            inputs = task_data[test_group].get("input", [])
            outputs = task_data[test_group].get("output", [])
            for inp, out in zip(inputs, outputs):
                stdin_data.append(inp)
                expected_outputs.append(out.strip())

    if not stdin_data:
        return {
            "status": "error",
            "is_correct": False,
            "message": "Task doesn't have test cases",
        }

    time_limit = task_data.get("time_limit")
    memory_limit = task_data.get("memory_limit_bytes")

    result = await run_in_docker(
        language=language,
        code=user_code,
        stdin_data=stdin_data,
        task_time_limit=time_limit,
        task_memory_limit_bytes=memory_limit,
    )

    if result["status"] != "success":
        return {
            "status": "error",
            "is_correct": False,
            "message": "Execution Error",
            "details": result.get("error", "Unknown error occurred"),
        }

    user_outputs = result.get("outputs", [])

    for idx, expected in enumerate(expected_outputs):
        test_input = stdin_data[idx]

        if idx >= len(user_outputs):
            return {
                "status": "failed",
                "is_correct": False,
                "message": f"Program crashed or terminated early on test case #{idx + 1}",
                "details": f"Input:\n{test_input}\n\nExpected:\n{expected}\n\nOutput:\n[No output]",
            }

        user_out = user_outputs[idx]

        if user_out != expected:
            return {
                "status": "failed",
                "is_correct": False,
                "message": f"Incorrect answer on test case #{idx + 1}",
                "details": f"Input:\n{test_input}\n\nExpected:\n{expected}\n\nOutput:\n{user_out}",
            }

    return {
        "status": "success",
        "is_correct": True,
        "message": "All test cases are successfully completed",
    }
