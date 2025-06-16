from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import ast
import pylint.lint
from pylint.reporters.text import TextReporter
import io
import tempfile
import os
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeInput(BaseModel):
    code: str

def set_parents(node, parent=None):
    for child in ast.iter_child_nodes(node):
        child.parent = node
        set_parents(child, node)

@app.post("/analyze")
async def analyze_code(data: CodeInput):
    code = data.code

    # Validate code before proceeding
    try:
        tree = ast.parse(code)
        set_parents(tree)  # Assign parents to AST nodes
    except SyntaxError:
        raise HTTPException(status_code=400, detail="Invalid Python code. Please enter valid code.")

    suggestions = []

    def get_nesting_level(n):
        level = 0
        while hasattr(n, 'parent'):
            n = n.parent
            level += 1
        return level

    # AST analysis
    for node in ast.walk(tree):
        # Existing checks
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call):
            func = getattr(node.iter.func, 'id', '')
            if func == 'range':
                suggestions.append("Consider using 'enumerate' instead of 'range(len(...))' for cleaner loops.")

        if isinstance(node, ast.FunctionDef) and len(node.body) > 20:
            suggestions.append(f"Function '{node.name}' is quite long. Consider refactoring.")

        # 1. Check for functions with too many arguments
        if isinstance(node, ast.FunctionDef):
            arg_count = len(node.args.args)
            if arg_count > 5:
                suggestions.append(f"Function '{node.name}' has {arg_count} arguments. Consider reducing the number of parameters for better readability.")

        # 2. Detect mutable default arguments (bad practice)
        if isinstance(node, ast.FunctionDef):
            defaults = node.args.defaults
            args = node.args.args[-len(defaults):] if defaults else []
            for arg, default in zip(args, defaults):
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    suggestions.append(f"Function '{node.name}' has mutable default argument '{arg.arg}'. Avoid using mutable defaults.")

        # 3. Detect deeply nested blocks (e.g., > 3 levels)
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            level = get_nesting_level(node)
            if level > 3:
                suggestions.append("Code is nested more than 3 levels deep. Consider refactoring to reduce complexity.")

        # 4. Detect functions without docstrings
        if isinstance(node, ast.FunctionDef):
            if ast.get_docstring(node) is None:
                suggestions.append(f"Function '{node.name}' is missing a docstring. Add one to improve code documentation.")

        # 5. Detect classes without docstrings
        if isinstance(node, ast.ClassDef):
            if ast.get_docstring(node) is None:
                suggestions.append(f"Class '{node.name}' is missing a docstring. Add one to improve code documentation.")

        # 6. Warn about usage of 'print' statements (could be for debugging)
        if isinstance(node, ast.Call):
            if getattr(node.func, 'id', None) == 'print':
                suggestions.append("Avoid using 'print' statements for debugging in production code. Consider using logging instead.")

    # Remove duplicate suggestions
    unique_suggestions = list(dict.fromkeys(suggestions))

    # Pylint analysis
    pylint_output = io.StringIO()
    reporter = TextReporter(output=pylint_output)
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
            tmp.write(code.encode('utf-8'))
            temp_file = tmp.name
        pylint.lint.Run([temp_file], reporter=reporter, exit=False)
    except Exception as e:
        unique_suggestions.append(f"Pylint error: {e}")
    finally:
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)

    pylint_results = pylint_output.getvalue().strip()

    # Extract the rating line from pylint output
    rating_match = re.search(r"Your code has been rated at ([0-9\.]+/10)", pylint_results)
    rating = rating_match.group(1) if rating_match else "No rating found."

    top_suggestion = unique_suggestions[0] if unique_suggestions else "No suggestion found."

    return {
        "suggestion": top_suggestion,
        "rating": rating
    }

# === Step 3: Run with uvicorn for deployment ===
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
