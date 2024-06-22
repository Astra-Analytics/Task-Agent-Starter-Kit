document.addEventListener("DOMContentLoaded", function () {
  function fetchTasks() {
    console.log("Fetching tasks...");
    fetch("/tasks")
      .then((response) => {
        console.log("Response received:", response);
        return response.json();
      })
      .then((data) => {
        console.log("Data received:", data);
        updateTasks(data.agent_tasks, "agent-tasks");
        updateTasks(data.human_tasks, "human-tasks");
      })
      .catch((error) => console.error("Error fetching tasks:", error));
  }

  function updateTasks(tasks, elementId) {
    const tasksList = document.getElementById(elementId);
    tasksList.innerHTML = "";

    tasks.forEach((task) => {
      const taskItem = document.createElement("li");
      taskItem.textContent = task.name;

      tasksList.appendChild(taskItem);

      if (task.potentialAction) {
        const subTasksList = document.createElement("ul");
        task.potentialAction.forEach((subtask) => {
          const subtaskItem = document.createElement("li");
          subtaskItem.textContent = subtask;
          subTasksList.appendChild(subtaskItem);
        });
        tasksList.appendChild(subTasksList);
      }
    });
  }

  // Fetch tasks every 10 seconds
  setInterval(fetchTasks, 5000);
  fetchTasks();
});
