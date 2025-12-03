import subprocess
import json
import sys
import os

# Define Test Cases
# Format: { 'variable': name, 'expected_file': filename_part, 'expected_lines': [list of lines], 'description': ... }
TEST_CASES = [
    {
        'variable': 'row_pointers',
        'expected_file': 'readpng.c',
        'expected_lines': [212, 221, 277, 296, 302],
        'description': 'Local pointer variable lifecycle (malloc, usage, free)'
    },
    {
        'variable': 'png_ptr',
        'expected_file': 'linux-auxv.c',
        'expected_lines': [39, 69, 77],
        'description': 'Function parameter usage'
    },
    {
        'variable': 'width',
        'expected_file': 'pngtest.c',
        'expected_lines': [1553], # Approximate check for assignment or usage
        'description': 'Local variable in pngtest'
    },
    {
        'variable': 'info_ptr',
        'expected_file': 'example.c',
        'expected_lines': [], # Just check if it finds anything in example.c
        'description': 'Struct pointer in example.c'
    }
]

def run_test(test_case):
    var_name = test_case['variable']
    expected_file = test_case['expected_file']
    print(f"Running test for '{var_name}' in '{expected_file}'...")
    
    try:
        # Run context_engine.py with JSON output and file filter
        cmd = [sys.executable, 'context_engine.py', var_name, '--json', '--file', expected_file]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse JSON
        # The script might print "Loading CPG..." to stdout before JSON, so we need to find the JSON part
        output = result.stdout
        json_start = output.find('{')
        if json_start == -1:
            print(f"  [FAIL] No JSON output found. Output:\n{output[:200]}...")
            return False
            
        json_str = output[json_start:]
        data = json.loads(json_str)
        
        # Verify
        files = data.get('files', {})
        found_file = False
        found_lines = 0
        total_expected = len(test_case['expected_lines'])
        
        print(f"  Slice size: {data.get('slice_size')} nodes")
        
        for filename, entries in files.items():
            if test_case['expected_file'] in filename:
                found_file = True
                print(f"  Found expected file: {filename}")
                
                # Check lines
                actual_lines = [e['line'] for e in entries]
                print(f"  Actual lines: {actual_lines}")
                
                for exp_line in test_case['expected_lines']:
                    if exp_line in actual_lines:
                        found_lines += 1
                    else:
                        print(f"  [MISS] Expected line {exp_line} not found.")
                        
        if not found_file:
            print(f"  [FAIL] Expected file '{test_case['expected_file']}' not found in slice.")
            return False
            
        if total_expected > 0:
            coverage = found_lines / total_expected
            print(f"  Coverage: {found_lines}/{total_expected} ({coverage:.0%})")
            if coverage < 0.5:
                print("  [FAIL] Low coverage (< 50%)")
                return False
        
        print("  [PASS]")
        return True

    except subprocess.CalledProcessError as e:
        print(f"  [ERROR] Script failed: {e}")
        print(e.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"  [ERROR] Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"  [ERROR] Unexpected error: {e}")
        return False

def main():
    print("=== Context Engine Evaluation ===")
    passed = 0
    total = len(TEST_CASES)
    
    for case in TEST_CASES:
        if run_test(case):
            passed += 1
        print("-" * 40)
        
    print(f"\nSummary: {passed}/{total} tests passed.")
    
if __name__ == "__main__":
    main()
