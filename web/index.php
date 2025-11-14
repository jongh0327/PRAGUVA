<?php include 'navbar.php'; ?>
<h1>Welcome to the Home Page</h1>
<p>Run the Python program with a parameter:</p>

<form action="run_python.php" method="post">
  <label>Enter a value:</label>
  <input type="text" name="user_input" required>
  <button type="submit">Run Python Program</button>
</form>