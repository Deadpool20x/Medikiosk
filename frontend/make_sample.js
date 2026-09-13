// Regenerate the synthetic prescription fixtures (delegated to the Python
// generator so the output is a real, decodable image rather than a placeholder).
const { execFileSync } = require('child_process');
const path = require('path');

execFileSync('python', [path.resolve(__dirname, '..', 'scripts', 'make_sample_prescription.py')], {
  cwd: path.resolve(__dirname, '..'),
  stdio: 'inherit',
});