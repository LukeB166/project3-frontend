const btn = document.getElementById("analyzeBtn");
const codeInput = document.getElementById("codeInput");
const suggestionOutput = document.getElementById("suggestion");
const ratingOutput = document.getElementById("rating");

btn.addEventListener("click", async (event) => {
  event.preventDefault();

  const code = codeInput.value.trim();
  if (!code) {
    alert("Please enter some Python code!");
    return;
  }

  try {
    const response = await fetch("https://project3-xfk2.onrender.com/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      suggestionOutput.textContent = errorData.detail || "An error occurred.";
      ratingOutput.textContent = "";
      return;
    }

    const data = await response.json();
    suggestionOutput.textContent = data.suggestion;
    ratingOutput.textContent = data.rating;
  } catch (error) {
    suggestionOutput.textContent = "Network or server error: " + error.message;
    ratingOutput.textContent = "";
  }
});
