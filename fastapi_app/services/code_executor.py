from infrastructure.sandbox.docker_runner import run_in_docker


async def execute_and_test_code(task_data: dict, language: str, user_code: str) -> dict:
    tests = []

    if "public_tests" in task_data:
        inputs = task_data["public_tests"].get("input", [])
        outputs = task_data["public_tests"].get("output", [])
        for i in range(len(inputs)):
            tests.append({"input": inputs[i], "output": outputs[i]})

    if "generated_tests" in task_data:
        inputs = task_data["generated_tests"].get("input", [])
        outputs = task_data["generated_tests"].get("output", [])
        for i in range(len(inputs)):
            tests.append({"input": inputs[i], "output": outputs[i]})

    if not tests:
        return {
            "status": "error",
            "is_correct": False,
            "message": "Task doesn't have test cases",
        }

    for idx, test in enumerate(tests):
        test_input = test["input"]
        expected_output = test["output"].strip()

        result = await run_in_docker(language, user_code, test_input)

        if result["status"] == "error":
            return {
                "status": "error",
                "is_correct": False,
                "message": f"Error while testing #{idx + 1} case: {result['error']}",
                "details": result["output"],
            }

        user_output = result["output"].strip()

        if user_output != expected_output:
            return {
                "status": "failed",
                "is_correct": False,
                "message": f"Incorrect answer on test case: {idx + 1}",
                "details": f"Input:\n{test_input}\n\nExpected:\n{expected_output}\n\nOutput:\n{user_output}",
            }

    return {
        "status": "success",
        "is_correct": True,
        "message": "All test cases are successfully completed",
    }
