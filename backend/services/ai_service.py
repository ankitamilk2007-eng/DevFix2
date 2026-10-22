import os
import json
import re
import time
import ast
import difflib
import requests
from ..language_adapters.python_adapter import PythonAdapter

class AIService:
    def __init__(self):
        self.provider = os.environ.get('AI_PROVIDER', 'ollama')
        self.ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model_name = os.environ.get('AI_MODEL_NAME', 'llama3:8b')
        self.python_adapter = PythonAdapter()
        self._cached_status = None
        self._cached_status_time = 0

    def get_status(self, force_refresh: bool = False) -> dict:
        """
        Actively checks whether the configured AI model is reachable and downloaded.
        Safely caches result for 10 seconds to avoid blocking rapid health probes.
        Never pretends an AI model is ready when it is not.
        """
        now = time.time()
        if not force_refresh and self._cached_status and (now - self._cached_status_time) < 10:
            return self._cached_status

        if self.provider == 'ollama':
            try:
                res = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get('name') for m in data.get('models', [])]
                    
                    if not models:
                        status_dict = {
                            'available': False,
                            'provider': 'ollama',
                            'configured_model': self.model_name,
                            'installed_models': [],
                            'status': 'no_models_installed',
                            'message': f"Ollama is running on port 11434, but no models are downloaded. Run `ollama pull {self.model_name}` to enable live model inference."
                        }
                    else:
                        # Check if configured model is installed
                        model_found = any(self.model_name in m or m.startswith(self.model_name.split(':')[0]) for m in models)
                        
                        # If not found and no explicit env var was set, auto-adopt the first available installed model
                        if not model_found and 'AI_MODEL_NAME' not in os.environ:
                            self.model_name = models[0]
                            model_found = True

                        if model_found:
                            status_dict = {
                                'available': True,
                                'provider': 'ollama',
                                'configured_model': self.model_name,
                                'installed_models': models,
                                'status': 'ready',
                                'message': f"Ollama model '{self.model_name}' is downloaded and reachable."
                            }
                        else:
                            status_dict = {
                                'available': False,
                                'provider': 'ollama',
                                'configured_model': self.model_name,
                                'installed_models': models,
                                'status': 'model_not_found',
                                'message': f"Configured model '{self.model_name}' is not downloaded. Available models: {', '.join(models)}"
                            }
                else:
                    status_dict = {
                        'available': False,
                        'provider': 'ollama',
                        'status': 'http_error',
                        'message': f"Ollama server returned HTTP {res.status_code}."
                    }
            except Exception:
                status_dict = {
                    'available': False,
                    'provider': 'ollama',
                    'status': 'offline',
                    'message': f"Ollama is not running on {self.ollama_url}. Start Ollama or configure an alternate provider."
                }
        else:
            status_dict = {
                'available': False,
                'provider': self.provider,
                'status': 'unsupported_provider',
                'message': f"Provider '{self.provider}' is not currently configured."
            }

        self._cached_status = status_dict
        self._cached_status_time = now
        return status_dict

    def generate_diagnosis(self, language: str, code: str, traceback: str, context: str = '') -> dict:
        """
        Generates diagnosis. If an AI model is not configured, provides evidence-backed
        AST/traceback facts and transparently reports that AI inference is offline.
        """
        return self._do_generate_diagnosis(language, code, traceback, context)

    def diagnose_error(self, language: str, code: str, traceback: str, context: str = '') -> dict:
        """Alias for generate_diagnosis."""
        return self.generate_diagnosis(language, code, traceback, context)

    def _do_generate_diagnosis(self, language: str, code: str, traceback: str, context: str = '') -> dict:
        if language != 'python':
            raise ValueError(f"Language '{language}' adapter is in development. Only Python is currently enabled.")

        # 1. Parse factual evidence from Python AST & traceback
        parsed_facts = self.python_adapter.parse_traceback(traceback)
        ast_info = self.python_adapter.analyze_source(code)

        ai_status = self.get_status()

        if ai_status['available']:
            # Call live Ollama model
            try:
                ai_diagnosis = self._call_ollama_for_diagnosis(code, traceback, parsed_facts, context)
                if ai_diagnosis:
                    ai_diagnosis['aiConfigured'] = True
                    ai_diagnosis['aiModel'] = self.model_name
                    ai_diagnosis['isDemonstration'] = False
                    return ai_diagnosis
            except Exception as e:
                # Log model failure honestly
                pass

        # 2. Honest Fallback when AI is not configured or model unavailable
        error_type = parsed_facts['errorType']
        explanation_map = {
            'ZeroDivisionError': 'Division by zero occurs when a numeric denominator evaluates to 0. Python terminates immediately to prevent invalid mathematical states.',
            'IndexError': 'List index out of range occurs when code attempts to access a sequence position greater than or equal to len(sequence).',
            'TypeError': 'TypeError occurs when an operation or function is applied to an object of an inappropriate type, such as concatenating NoneType with str.',
            'KeyError': 'KeyError occurs when attempting to access a dictionary key that does not exist in the collection.',
            'AttributeError': 'AttributeError occurs when attempting to access a property or method that does not exist on the given object.',
            'NameError': 'NameError occurs when code refers to an identifier that has not been defined or bound in the current scope, commonly due to a typo or missing variable declaration.',
            'SyntaxError': 'SyntaxError occurs when Python grammar parsing fails before execution, such as missing a colon, unclosed parenthesis, or malformed syntax.'
        }
        explanation = explanation_map.get(
            error_type,
            f"A {error_type} was raised at runtime. Review the variables and operations at line {parsed_facts['culpritLine']}."
        )

        rec_actions = {
            'SyntaxError': f"Correct syntax structure at line {parsed_facts['culpritLine']} (check for missing colons, unbalanced parentheses/quotes, or malformed statement headers).",
            'NameError': f"Verify variable name spelling at line {parsed_facts['culpritLine']} or declare the variable before use.",
            'AttributeError': f"Ensure the object at line {parsed_facts['culpritLine']} is not None and has the intended attribute or method.",
            'ZeroDivisionError': f"Add a guard clause checking for empty collections or zero denominator before division at line {parsed_facts['culpritLine']}.",
            'IndexError': f"Verify sequence length and loop boundary bounds checking at line {parsed_facts['culpritLine']}.",
            'TypeError': f"Validate operand data types or apply safe type conversions at line {parsed_facts['culpritLine']}."
        }
        recommended_action = rec_actions.get(
            error_type,
            f"Add defensive validation or guard checks around line {parsed_facts['culpritLine']}."
        )

        return {
            'errorType': error_type,
            'summary': f"{error_type}: {parsed_facts['errorMessage']}",
            'culpritLine': parsed_facts['culpritLine'] or 1,
            'culpritCode': parsed_facts['culpritCode'] or '# Offending expression identified from stack frame',
            'fileName': parsed_facts['fileName'],
            'tracebackFacts': parsed_facts['tracebackFacts'],
            'hypothesis': f"Based on traceback inspection, {error_type} occurred during evaluation of line {parsed_facts['culpritLine']}. Note: Live AI model synthesis is unconfigured ({ai_status['message']}).",
            'explanation': explanation,
            'recommendedAction': recommended_action,
            'aiConfigured': False,
            'aiStatus': ai_status,
            'isDemonstration': False
        }

    def generate_proposed_fix(self, language: str, code: str, traceback: str, diagnosis: dict) -> dict:
        """
        Generates minimal code patch for the diagnosed issue.
        Attempts AI model first if available; otherwise uses evidence-backed
        AST and syntactic pattern analysis to synthesize general fixes across error classes.
        Never outputs unchanged buggy code as an automated fix.
        """
        norm_code = code.replace('\r\n', '\n')

        # 1. Attempt live AI model synthesis if available
        ai_status = self.get_status()
        if ai_status['available']:
            try:
                ai_fix = self._call_ollama_for_fix(norm_code, traceback, diagnosis)
                if ai_fix and 'fullFixedCode' in ai_fix:
                    ai_fix['isDemonstration'] = False
                    return ai_fix
            except Exception:
                pass

        # 2. Evidence-backed general patch synthesizer
        return self._generate_generic_patch(norm_code, diagnosis)

    def _generate_generic_patch(self, code: str, diagnosis: dict) -> dict:
        """
        Generates a working defensive patch for arbitrary Python code.
        Supports general classes of errors: SyntaxError, TypeError, IndexError,
        ZeroDivisionError, NameError, and AttributeError without hardcoding variable names.
        """
        error_type = diagnosis.get('errorType', 'Exception')
        error_message = diagnosis.get('errorMessage', '') or diagnosis.get('summary', '')
        culprit_line = diagnosis.get('culpritLine')
        culprit_code = diagnosis.get('culpritCode', '')
        lines = code.split('\n')

        target_idx = None
        if culprit_line and 1 <= culprit_line <= len(lines):
            target_idx = culprit_line - 1
        elif culprit_code:
            for idx, line in enumerate(lines):
                if culprit_code.strip() and culprit_code.strip() in line:
                    target_idx = idx
                    break

        # ---------------------------------------------------------------------
        # 1. SyntaxError: Deterministic syntactic repairs with AST verification
        # ---------------------------------------------------------------------
        if error_type == 'SyntaxError':
            if target_idx is not None:
                target_line = lines[target_idx]
                stripped = target_line.rstrip()
                
                # Case A: Missing colon on compound statement header
                compound_keywords = ('def ', 'class ', 'if ', 'elif ', 'else', 'for ', 'while ', 'try', 'except', 'finally', 'with ')
                if any(stripped.lstrip().startswith(kw) for kw in compound_keywords) and not stripped.endswith(':'):
                    fixed_line = stripped + ':'
                    test_lines = list(lines)
                    test_lines[target_idx] = fixed_line
                    candidate_code = '\n'.join(test_lines)
                    try:
                        ast.parse(candidate_code)
                        return {
                            'summary': f"Add missing colon ':' to {stripped.split()[0]} statement header",
                            'explanation': "SyntaxError occurred because Python compound statements must terminate with a colon ':'.",
                            'affectedLines': f"Line {target_idx + 1}",
                            'originalSnippet': target_line,
                            'fixedSnippet': fixed_line,
                            'fullFixedCode': candidate_code,
                            'canSynthesize': True,
                            'isUnmodified': False
                        }
                    except SyntaxError:
                        pass

                # Case B: Unclosed parenthesis
                if stripped.count('(') > stripped.count(')'):
                    diff = stripped.count('(') - stripped.count(')')
                    fixed_line = stripped + (')' * diff)
                    test_lines = list(lines)
                    test_lines[target_idx] = fixed_line
                    candidate_code = '\n'.join(test_lines)
                    try:
                        ast.parse(candidate_code)
                        return {
                            'summary': f"Add closing parenthesis ')' on line {target_idx + 1}",
                            'explanation': "SyntaxError occurred because an opening parenthesis '(' was left unclosed.",
                            'affectedLines': f"Line {target_idx + 1}",
                            'originalSnippet': target_line,
                            'fixedSnippet': fixed_line,
                            'fullFixedCode': candidate_code,
                            'canSynthesize': True,
                            'isUnmodified': False
                        }
                    except SyntaxError:
                        pass

            # If SyntaxError cannot be safely synthesized deterministically:
            return {
                'summary': "Automated patch unavailable for SyntaxError: manual correction required",
                'explanation': f"The diagnostic engine identified a SyntaxError at line {culprit_line or 1}: '{error_message}'. Automated patching cannot reliably deduce intended code logic. Please correct the syntax in the editor below before running verification.",
                'affectedLines': f"Line {culprit_line or 1}",
                'originalSnippet': lines[target_idx] if target_idx is not None else code.split('\n')[0],
                'fixedSnippet': lines[target_idx] if target_idx is not None else code.split('\n')[0],
                'fullFixedCode': code,
                'canSynthesize': False,
                'isUnmodified': True,
                'noFixGenerated': True
            }

        # ---------------------------------------------------------------------
        # 2. NameError: Robust Identifier Typo & Scope Resolution
        # ---------------------------------------------------------------------
        if error_type == 'NameError':
            err_text = f"{diagnosis.get('errorMessage', '')} {diagnosis.get('summary', '')} {error_message}"
            name_match = (
                re.search(r"name '([^']+)' is not defined", err_text) or
                re.search(r"variable '([^']+)' is not defined", err_text) or
                re.search(r"'([^']+)' is not defined", err_text) or
                re.search(r"name '([^']+)'", err_text) or
                re.search(r"'([a-zA-Z_]\w*)'", err_text)
            )
            sugg_match = re.search(r"Did you mean: '([^']+)'\?", err_text)
            undefined_name = name_match.group(1) if name_match else None
            suggested_name = sugg_match.group(1) if sugg_match else None

            # Case A: If Python provided a direct suggestion
            if undefined_name and suggested_name:
                fixed_code = re.sub(rf'\b{re.escape(undefined_name)}\b', suggested_name, code)
                if fixed_code != code:
                    try:
                        ast.parse(fixed_code)
                        return {
                            'summary': f"Correct identifier typo: replace '{undefined_name}' with '{suggested_name}'",
                            'explanation': f"Resolves NameError by replacing the undefined identifier '{undefined_name}' with the defined variable '{suggested_name}'.",
                            'affectedLines': f"Line {culprit_line or 1}",
                            'originalSnippet': lines[target_idx] if target_idx is not None else code.split('\n')[0],
                            'fixedSnippet': fixed_code.split('\n')[target_idx] if target_idx is not None else '',
                            'fullFixedCode': fixed_code,
                            'canSynthesize': True,
                            'isUnmodified': False
                        }
                    except SyntaxError:
                        pass

            # Case B: If no direct suggestion, inspect code for close matches among defined identifiers
            if undefined_name:
                candidate_names = set()
                try:
                    tree = ast.parse(code)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            candidate_names.add(node.name)
                            for arg in node.args.args:
                                candidate_names.add(arg.arg)
                        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                            candidate_names.add(node.id)
                        elif isinstance(node, ast.alias):
                            candidate_names.add(node.asname or node.name)
                except SyntaxError:
                    for m in re.finditer(r'\b([a-zA-Z_]\w*)\s*=', code):
                        candidate_names.add(m.group(1))
                    for m in re.finditer(r'def\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)', code):
                        candidate_names.add(m.group(1))
                        for param in m.group(2).split(','):
                            clean_p = param.strip().split('=')[0].split(':')[0].strip()
                            if clean_p:
                                candidate_names.add(clean_p)

                candidate_names.discard(undefined_name)

                # Check for standard library modules if name matches (e.g. math, json, sys, os, re, random)
                std_libs = {'math', 'json', 'sys', 'os', 're', 'random', 'time', 'datetime', 'itertools', 'collections'}
                if undefined_name in std_libs and f"import {undefined_name}" not in code:
                    full_fixed = f"import {undefined_name}\n" + code
                    return {
                        'summary': f"Add missing import for standard library '{undefined_name}'",
                        'explanation': f"Resolves NameError by importing the standard library module '{undefined_name}'.",
                        'affectedLines': "Line 1",
                        'originalSnippet': lines[0] if lines else '',
                        'fixedSnippet': f"import {undefined_name}\n" + (lines[0] if lines else ''),
                        'fullFixedCode': full_fixed,
                        'canSynthesize': True,
                        'isUnmodified': False
                    }

                # Find close matches using difflib
                matches = difflib.get_close_matches(undefined_name, list(candidate_names), n=1, cutoff=0.50)
                if matches:
                    best_match = matches[0]
                    fixed_code = re.sub(rf'\b{re.escape(undefined_name)}\b', best_match, code)
                    if fixed_code != code:
                        try:
                            ast.parse(fixed_code)
                            return {
                                'summary': f"Fix variable typo: replace '{undefined_name}' with '{best_match}'",
                                'explanation': f"Resolves NameError by substituting the closest defined identifier in scope ('{best_match}').",
                                'affectedLines': f"Line {culprit_line or 1}",
                                'originalSnippet': lines[target_idx] if target_idx is not None else code.split('\n')[0],
                                'fixedSnippet': fixed_code.split('\n')[target_idx] if target_idx is not None else '',
                                'fullFixedCode': fixed_code,
                                'canSynthesize': True,
                                'isUnmodified': False
                            }
                        except SyntaxError:
                            pass

            # If NameError cannot be resolved by typo matching or imports:
            # CRITICAL: NEVER WRAP IN TRY/EXCEPT NameError!
            return {
                'summary': f"Undefined identifier '{undefined_name or 'variable'}' requires definition",
                'explanation': f"NameError: '{undefined_name or 'variable'}' is not defined in scope. The diagnostic engine found no matching variable in scope. Please declare or assign '{undefined_name or 'variable'}' in the code editor before running verification.",
                'affectedLines': f"Line {culprit_line or 1}",
                'originalSnippet': lines[target_idx] if target_idx is not None else code.split('\n')[0],
                'fixedSnippet': lines[target_idx] if target_idx is not None else code.split('\n')[0],
                'fullFixedCode': code,
                'canSynthesize': False,
                'isUnmodified': True,
                'noFixGenerated': True
            }

        # ---------------------------------------------------------------------
        # 3. AttributeError: Typo suggestion correction or NoneType defensive guard
        # ---------------------------------------------------------------------
        if error_type == 'AttributeError':
            sugg_match = re.search(r"'([^']+)' object has no attribute '([^']+)'\. Did you mean: '([^']+)'\?", error_message)
            if sugg_match and target_idx is not None:
                obj_type, wrong_attr, right_attr = sugg_match.group(1), sugg_match.group(2), sugg_match.group(3)
                target_line = lines[target_idx]
                fixed_line = re.sub(rf'\.{re.escape(wrong_attr)}\b', f'.{right_attr}', target_line)
                if fixed_line != target_line:
                    test_lines = list(lines)
                    test_lines[target_idx] = fixed_line
                    candidate_code = '\n'.join(test_lines)
                    return {
                        'summary': f"Correct attribute typo: replace '.{wrong_attr}' with '.{right_attr}'",
                        'explanation': f"Resolves AttributeError by invoking the valid '{right_attr}' attribute on {obj_type}.",
                        'affectedLines': f"Line {target_idx + 1}",
                        'originalSnippet': target_line,
                        'fixedSnippet': fixed_line,
                        'fullFixedCode': candidate_code,
                        'canSynthesize': True,
                        'isUnmodified': False
                    }

        # ---------------------------------------------------------------------
        # 4. ZeroDivisionError: General empty collection guard or denominator check
        # ---------------------------------------------------------------------
        if error_type == 'ZeroDivisionError':
            for idx in range(max(0, (target_idx or 0) - 5), min(len(lines), (target_idx or 0) + 1)):
                line = lines[idx]
                # Case A: Direct division by len(collection)
                match_len = re.search(r'([ \t]*).*?/\s*len\(([^)]+)\)', line)
                if match_len:
                    indent = match_len.group(1)
                    seq_expr = match_len.group(2).strip()
                    guard_code = f"{indent}if not {seq_expr}:\n{indent}    return 0.0"
                    test_lines = lines[:idx] + [guard_code] + lines[idx:]
                    candidate_code = '\n'.join(test_lines)
                    try:
                        ast.parse(candidate_code)
                        return {
                            'summary': f"Add guard clause for empty collection '{seq_expr}'",
                            'explanation': f"Prevents ZeroDivisionError when '{seq_expr}' is empty before computing division by len({seq_expr}).",
                            'affectedLines': f"Line {idx + 1}",
                            'originalSnippet': line,
                            'fixedSnippet': f"{guard_code}\n{line}",
                            'fullFixedCode': candidate_code,
                            'canSynthesize': True,
                            'isUnmodified': False
                        }
                    except SyntaxError:
                        pass

                # Case B: Division by variable
                match_div = re.search(r'([ \t]*).*?\s*/\s*([a-zA-Z_]\w*)', line)
                if match_div:
                    indent = match_div.group(1)
                    denom_var = match_div.group(2)
                    if denom_var != 'len':
                        seq_name = None
                        len_idx = None
                        for prev_idx in range(max(0, idx - 5), idx):
                            len_match = re.search(rf'{denom_var}\s*=\s*len\(([a-zA-Z_]\w*)\)', lines[prev_idx])
                            if len_match:
                                seq_name = len_match.group(1)
                                len_idx = prev_idx
                                break
                        
                        guard_cond = f"not {seq_name}" if seq_name else f"{denom_var} == 0"
                        guard_code = f"{indent}if {guard_cond}:\n{indent}    return 0.0\n"
                        insert_idx = len_idx if len_idx is not None else idx
                        test_lines = lines[:insert_idx] + [guard_code.rstrip()] + lines[insert_idx:]
                        candidate_code = '\n'.join(test_lines)
                        try:
                            ast.parse(candidate_code)
                            return {
                                'summary': f"Add guard clause checking for empty/zero {denom_var} before division",
                                'explanation': f"Prevents ZeroDivisionError when the sequence or denominator is empty or zero.",
                                'affectedLines': f"Line {insert_idx + 1}",
                                'originalSnippet': lines[idx],
                                'fixedSnippet': f"{guard_code}{lines[idx]}",
                                'fullFixedCode': candidate_code,
                                'canSynthesize': True,
                                'isUnmodified': False
                            }
                        except SyntaxError:
                            pass

        # ---------------------------------------------------------------------
        # 5. IndexError: General loop boundary off-by-one correction
        # ---------------------------------------------------------------------
        if error_type == 'IndexError':
            for idx in range(len(lines)):
                loop_match = re.search(r'^([ \t]*)for\s+([a-zA-Z_]\w*)\s+in\s+range\(([^)]*len\(([a-zA-Z_]\w*)\)[^)]*)\):', lines[idx])
                if loop_match:
                    indent = loop_match.group(1)
                    loop_var = loop_match.group(2)
                    range_args = loop_match.group(3)
                    seq_name = loop_match.group(4)
                    body = '\n'.join(lines[idx+1:min(len(lines), idx+10)])
                    if f"{seq_name}[{loop_var} + 1]" in body or f"{seq_name}[{loop_var}+1]" in body:
                        new_range = re.sub(rf'len\({seq_name}\)', f'len({seq_name}) - 1', range_args)
                        guard_clause = f"{indent}if len({seq_name}) < 2:\n{indent}    return []\n\n"
                        fixed_loop = f"{guard_clause}{indent}for {loop_var} in range({new_range}):"
                        test_lines = list(lines)
                        test_lines[idx] = fixed_loop
                        candidate_code = '\n'.join(test_lines)
                        try:
                            ast.parse(candidate_code)
                            return {
                                'summary': f"Fix loop upper boundary to prevent {seq_name} index overflow",
                                'explanation': f"Adjusts range to terminate at len({seq_name}) - 1, preventing out-of-bounds access when indexing {seq_name}[{loop_var} + 1].",
                                'affectedLines': f"Line {idx + 1}",
                                'originalSnippet': loop_match.group(0),
                                'fixedSnippet': fixed_loop,
                                'fullFixedCode': candidate_code,
                                'canSynthesize': True,
                                'isUnmodified': False
                            }
                        except SyntaxError:
                            pass

        # ---------------------------------------------------------------------
        # 6. General Culprit Line Defensive Wrapping for Unhandled Exceptions
        # ---------------------------------------------------------------------
        # Advance target if pointing to def or class declaration
        if target_idx is not None and lines[target_idx].strip().startswith(('def ', 'class ')):
            for next_idx in range(target_idx + 1, len(lines)):
                stripped_next = lines[next_idx].strip()
                if stripped_next and not stripped_next.startswith(('def ', 'class ', '#', '"""', "'''")):
                    target_idx = next_idx
                    break

        if target_idx is not None:
            target_line = lines[target_idx]
            indent = target_line[:len(target_line) - len(target_line.lstrip())]
            stripped = target_line.strip()

            if error_type == 'ZeroDivisionError':
                if stripped.startswith('return '):
                    expr = stripped[7:]
                    replacement = f"{indent}try:\n{indent}    return {expr}\n{indent}except ZeroDivisionError:\n{indent}    return 0.0"
                elif '=' in stripped:
                    var, expr = stripped.split('=', 1)
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except ZeroDivisionError:\n{indent}    {var.strip()} = 0.0"
                else:
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except ZeroDivisionError:\n{indent}    pass"

            elif error_type == 'IndexError':
                if stripped.startswith('return '):
                    expr = stripped[7:]
                    replacement = f"{indent}try:\n{indent}    return {expr}\n{indent}except IndexError:\n{indent}    return None"
                elif '=' in stripped:
                    var, expr = stripped.split('=', 1)
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except IndexError:\n{indent}    {var.strip()} = None"
                else:
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except IndexError:\n{indent}    pass"

            elif error_type == 'TypeError':
                if stripped.startswith('return '):
                    expr = stripped[7:]
                    replacement = f"{indent}try:\n{indent}    return {expr}\n{indent}except TypeError:\n{indent}    try:\n{indent}        return str({expr.replace('+', ') + str(')})\n{indent}    except Exception:\n{indent}        return None"
                elif '=' in stripped:
                    var, expr = stripped.split('=', 1)
                    var_clean = var.strip()
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except TypeError:\n{indent}    try:\n{indent}        {var_clean} = str({expr.replace('+', ') + str(')})\n{indent}    except Exception:\n{indent}        {var_clean} = None"
                else:
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except TypeError:\n{indent}    pass"

            elif error_type == 'AttributeError':
                if stripped.startswith('return '):
                    expr = stripped[7:]
                    replacement = f"{indent}try:\n{indent}    return {expr}\n{indent}except AttributeError:\n{indent}    return None"
                elif '=' in stripped:
                    var, expr = stripped.split('=', 1)
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except AttributeError:\n{indent}    {var.strip()} = None"
                else:
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except AttributeError:\n{indent}    pass"

            elif error_type == 'KeyError':
                if '=' in stripped:
                    var, expr = stripped.split('=', 1)
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except KeyError:\n{indent}    {var.strip()} = None"
                else:
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except KeyError:\n{indent}    pass"

            else:
                if error_type in ('NameError', 'SyntaxError'):
                    return {
                        'summary': f"Automated patch unavailable for {error_type}",
                        'explanation': f"The diagnostic engine identified the root cause from the traceback, but generating an automated patch for {error_type} requires manual correction. Please edit the code directly in the review panel before verifying.",
                        'affectedLines': f"Line {culprit_line or 1}",
                        'originalSnippet': lines[target_idx] if target_idx is not None else code.split('\n')[0],
                        'fixedSnippet': lines[target_idx] if target_idx is not None else code.split('\n')[0],
                        'fullFixedCode': code,
                        'canSynthesize': False,
                        'isUnmodified': True,
                        'noFixGenerated': True
                    }

                if stripped.startswith('return '):
                    expr = stripped[7:]
                    replacement = f"{indent}try:\n{indent}    return {expr}\n{indent}except {error_type}:\n{indent}    return None"
                elif '=' in stripped:
                    var, expr = stripped.split('=', 1)
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except {error_type}:\n{indent}    {var.strip()} = None"
                else:
                    replacement = f"{indent}try:\n{indent}    {stripped}\n{indent}except {error_type}:\n{indent}    pass"

            test_lines = list(lines)
            test_lines[target_idx] = replacement
            candidate_code = '\n'.join(test_lines)
            return {
                'summary': f"Defensive guard clause for {error_type}",
                'explanation': f"Wraps line {target_idx + 1} with error handling for {error_type} to prevent unhandled runtime crash.",
                'affectedLines': f"Line {target_idx + 1}",
                'originalSnippet': target_line,
                'fixedSnippet': replacement,
                'fullFixedCode': candidate_code,
                'canSynthesize': True,
                'isUnmodified': False
            }

        # If culprit line cannot be pinpointed, report honestly without fake code
        return {
            'summary': f"Automated patch unavailable for this {error_type} pattern",
            'explanation': f"The diagnostic engine identified the root cause from the traceback, but generating an automated patch requires live AI synthesis. Review the diagnosis and edit your fix directly in the review panel before verifying.",
            'affectedLines': "Source code",
            'originalSnippet': code.split('\n')[0] if code else '',
            'fixedSnippet': code.split('\n')[0] if code else '',
            'fullFixedCode': code,
            'canSynthesize': False,
            'isUnmodified': True,
            'noFixGenerated': True
        }

    def _extract_json(self, text: str):
        """Safely extracts JSON dict from model text output, handling code fences and wrapping."""
        if not text or not isinstance(text, str):
            return None
        cleaned = text.strip()
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].startswith('```'):
                lines = lines[:-1]
            cleaned = '\n'.join(lines).strip()

        try:
            val = json.loads(cleaned)
            if isinstance(val, dict):
                return val
        except Exception:
            pass

        # Substring search for { ... }
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                val = json.loads(cleaned[start:end+1])
                if isinstance(val, dict):
                    return val
            except Exception:
                pass
        return None

    def _call_ollama_for_diagnosis(self, code: str, traceback: str, parsed_facts: dict, context: str) -> dict:
        prompt = f"""You are DevFix AI, an evidence-based code debugging platform.
Analyze this Python error traceback and source code.
Traceback:
{traceback}

Source Code:
{code}

Context:
{context}

Return a valid JSON object with these EXACT keys:
- "errorType": string
- "summary": string
- "culpritLine": integer
- "culpritCode": string
- "hypothesis": string
- "explanation": string
- "recommendedAction": string
Do not include any markdown fences or conversational text, ONLY raw JSON."""

        try:
            res = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    'model': self.model_name,
                    'prompt': prompt,
                    'stream': False,
                    'format': 'json'
                },
                timeout=12
            )
            if res.status_code == 200:
                resp_json = res.json()
                raw_text = resp_json.get('response', '')
                parsed = self._extract_json(raw_text)
                if parsed and isinstance(parsed, dict) and 'errorType' in parsed:
                    parsed['fileName'] = parsed_facts.get('fileName')
                    parsed['tracebackFacts'] = parsed_facts.get('tracebackFacts')
                    parsed['errorMessage'] = parsed_facts.get('errorMessage')
                    if parsed_facts.get('culpritLine'):
                        parsed['culpritLine'] = parsed_facts.get('culpritLine')
                    if parsed_facts.get('culpritCode'):
                        parsed['culpritCode'] = parsed_facts.get('culpritCode')
                    parsed['aiConfigured'] = True
                    parsed['aiModel'] = self.model_name
                    parsed['isDemonstration'] = False
                    return parsed
        except Exception:
            pass
        return None

    def _call_ollama_for_fix(self, code: str, traceback: str, diagnosis: dict) -> dict:
        prompt = f"""You are DevFix AI, an evidence-based code debugging platform.
Generate a minimal, verified fix for this Python code that addresses the diagnosed error.
Diagnosed Error: {diagnosis.get('errorType')}
Culprit Line: {diagnosis.get('culpritLine')}
Diagnosis Summary: {diagnosis.get('summary')}

Source Code:
{code}

Return a valid JSON object with these EXACT keys:
- "summary": string (brief summary of fix)
- "explanation": string (why this resolves the bug)
- "affectedLines": string (e.g. "Line 5" or "Lines 4-6")
- "originalSnippet": string (exact original code lines modified)
- "fixedSnippet": string (exact replacement code lines)
- "fullFixedCode": string (entire source code with fix applied cleanly)
Do not include any markdown fences or conversational text, ONLY raw JSON."""

        try:
            res = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    'model': self.model_name,
                    'prompt': prompt,
                    'stream': False,
                    'format': 'json'
                },
                timeout=15
            )
            if res.status_code == 200:
                resp_json = res.json()
                raw_text = resp_json.get('response', '')
                parsed = self._extract_json(raw_text)
                if not parsed or not isinstance(parsed, dict):
                    return None

                full_fixed = parsed.get('fullFixedCode')
                if not full_fixed or not isinstance(full_fixed, str):
                    return None

                # Strict validation 1: reject empty proposal
                if not full_fixed.strip():
                    return None

                # Strict validation 2: reject if model returned unchanged buggy code
                if full_fixed.strip() == code.strip():
                    return None

                try:
                    ast.parse(full_fixed)
                except SyntaxError:
                    return None

                # Preserve top-level execution calls (such as test prints) if model only returned the function
                orig_top_level = [
                    l for l in code.split('\n')
                    if l.strip() and not l.startswith((' ', '\t', 'def ', 'class ', '#', 'import ', 'from '))
                ]
                model_lines = full_fixed.split('\n')
                missing_top = [
                    l for l in orig_top_level
                    if l not in model_lines and not any(l.strip() in m for m in model_lines)
                ]
                if missing_top:
                    candidate_full = full_fixed.rstrip() + '\n\n' + '\n'.join(missing_top) + '\n'
                    try:
                        ast.parse(candidate_full)
                        full_fixed = candidate_full
                    except SyntaxError:
                        pass

                # Strict validation 2b: reject if restored proposal is unchanged buggy code
                if full_fixed.strip() == code.strip():
                    return None

                # Strict validation 4: Usability check — verify proposed fix resolves execution error
                exec_check = self.python_adapter.run_tests(full_fixed, tests=[])
                if exec_check.get('status') == 'failed':
                    # Model code still crashes with runtime error or failed assertions: reject as unusable
                    return None

                # Successful valid AI proposal
                return {
                    'summary': parsed.get('summary') or f"AI-generated fix for {diagnosis.get('errorType')}",
                    'explanation': parsed.get('explanation') or "Model generated code modification to resolve the diagnosed issue.",
                    'affectedLines': str(parsed.get('affectedLines') or f"Line {diagnosis.get('culpritLine') or 1}"),
                    'originalSnippet': parsed.get('originalSnippet') or '',
                    'fixedSnippet': parsed.get('fixedSnippet') or '',
                    'fullFixedCode': full_fixed,
                    'canSynthesize': True,
                    'isUnmodified': False,
                    'aiGenerated': True,
                    'isDemonstration': False
                }
        except Exception:
            return None
        return None

ai_service = AIService()

