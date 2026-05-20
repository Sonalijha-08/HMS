const { spawn } = require('child_process');
const path = require('path');

module.exports.sendEmail = async (event) => {
  console.log("Serverless trigger received:", event.body);
  
  return new Promise((resolve, reject) => {
    // Determine python command (Windows uses python, Unix often python3)
    const pyCommand = process.platform === 'win32' ? 'python' : 'python3';
    const pyScript = path.join(__dirname, 'handler.py');
    
    // Spawn python process to execute the python handler
    const py = spawn(pyCommand, [pyScript]);
    
    let stdoutData = '';
    let stderrData = '';
    
    // Write event to stdin for python script to read
    py.stdin.write(JSON.stringify(event));
    py.stdin.end();
    
    py.stdout.on('data', (data) => {
      stdoutData += data.toString();
    });
    
    py.stderr.on('data', (data) => {
      stderrData += data.toString();
    });
    
    py.on('close', (code) => {
      console.log(`Python process exited with code ${code}`);
      if (stderrData) {
        console.error(`Python stderr: ${stderrData}`);
      }
      
      try {
        if (code !== 0) {
          resolve({
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              error: 'Python handler error',
              code: code,
              stderr: stderrData
            })
          });
          return;
        }
        
        // Parse python output which is expected to be a JSON string response
        const response = JSON.parse(stdoutData.trim());
        resolve(response);
      } catch (err) {
        console.error("Failed to parse Python stdout:", stdoutData);
        resolve({
          statusCode: 500,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            error: 'Failed to parse python handler output',
            stdout: stdoutData,
            stderr: stderrData,
            exception: err.message
          })
        });
      }
    });
  });
};
