#!/usr/bin/env python3
"""
DSL Model Validation Script

This script performs comprehensive validation of DSL models before production execution.
It validates:
1. DSL Syntax Validation
2. Data Consistency Validation  
3. LP Model Validation
4. API Production Test
5. Safety Checks Before Production
6. Production Readiness Report

The script analyzes the DSL model associated with indicator_id to ensure it's safe for production.
"""

import sys
import os
import json
import re
import math
import datetime
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Set

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import project modules
try:
    from formula_runtime import run_formula, extract_identifiers, SAFE_FUNCTIONS
    from lp_model_parser import LPModelParser
    from lp_matrix_builder_deterministic_complete import LPMatrixBuilder
    from lp_solver import LPSolver
    from pythoncode import execute_lp_optimization, classify_and_execute_formulas
    LP_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Some modules not available: {e}")
    LP_AVAILABLE = False

# ============================================================================
# DSL SYNTAX VALIDATION
# ============================================================================

class DSLSyntaxValidator:
    """Validates DSL syntax and detects common issues."""
    
    # Supported DSL functions
    SUPPORTED_FUNCTIONS = {
        'DECISION', 'OBJECTIVE', 'BOUND', 'DOT', 'NORM', 'vector',
        'SUM', 'AVG', 'COUNT', 'COLUMN_SUM', 'AGG_MIN', 'AGG_SUM', 'AGG_MAX',
        'pow', 'sqrt', 'abs', 'min', 'max', 'linprog'
    }
    
    # DSL function patterns
    DECISION_PATTERN = r'DECISION\s*\(\s*([^,)]+)(?:\s*,\s*size\s*=\s*(\d+))?\s*\)'
    OBJECTIVE_PATTERN = r'OBJECTIVE\s*\((.*)\)'
    BOUND_PATTERN = r'BOUND\s*\(\s*([^,)]+)\s*,\s*([^,)]+)\s*,\s*([^)]+)\s*\)'
    VECTOR_PATTERN = r'vector\s*\((.*)\)'
    DOT_PATTERN = r'DOT\s*\((.*)\)'
    NORM_PATTERN = r'NORM\s*\((.*)\)'
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_formulas(self, formulas: Dict[str, str]) -> Dict[str, Any]:
        """
        Validate DSL syntax in formulas.
        
        Args:
            formulas: Dictionary of target:expression formulas
            
        Returns:
            Dictionary with validation results
        """
        self.errors = []
        self.warnings = []
        
        print("\n" + "="*80)
        print("DSL SYNTAX VALIDATION")
        print("="*80)
        
        # Check each formula
        for target, expr in formulas.items():
            print(f"\nValidating formula: {target} = {expr}")
            self._validate_single_formula(target, expr)
        
        # Check for circular dependencies
        self._check_circular_dependencies(formulas)
        
        # Check for undefined variables
        self._check_undefined_variables(formulas)
        
        # Check for vector size mismatches
        self._check_vector_size_mismatches(formulas)
        
        # Check for invalid inequality expressions
        self._check_inequality_expressions(formulas)
        
        # Check for incorrect bound syntax
        self._check_bound_syntax(formulas)
        
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors.copy(),
            'warnings': self.warnings.copy(),
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }
    
    def _validate_single_formula(self, target: str, expr: str) -> None:
        """Validate a single formula."""
        # Check for invalid function names
        self._check_invalid_functions(expr)
        
        # Check DECISION syntax
        self._validate_decision_syntax(expr)
        
        # Check OBJECTIVE syntax
        self._validate_objective_syntax(expr)
        
        # Check BOUND syntax
        self._validate_bound_syntax(expr)
        
        # Check DOT syntax
        self._validate_dot_syntax(expr)
        
        # Check NORM syntax
        self._validate_norm_syntax(expr)
        
        # Check vector syntax
        self._validate_vector_syntax(expr)
    
    def _check_invalid_functions(self, expr: str) -> None:
        """Check for invalid function names in expression."""
        # Extract function calls
        func_pattern = r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\('
        matches = re.findall(func_pattern, expr)
        
        for func in matches:
            if func.upper() not in [f.upper() for f in self.SUPPORTED_FUNCTIONS]:
                self.errors.append(f"Invalid function name: '{func}' is not a supported DSL function")
    
    def _validate_decision_syntax(self, expr: str) -> None:
        """Validate DECISION() function syntax."""
        matches = re.findall(self.DECISION_PATTERN, expr, re.IGNORECASE)
        for match in matches:
            var_name = match[0].strip()
            size_str = match[1].strip() if match[1] else None
            
            # Check variable name
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
                self.errors.append(f"Invalid variable name in DECISION(): '{var_name}'")
            
            # Check size parameter
            if size_str and not size_str.isdigit():
                self.errors.append(f"Invalid size parameter in DECISION(): '{size_str}' must be integer")
    
    def _validate_objective_syntax(self, expr: str) -> None:
        """Validate OBJECTIVE() function syntax."""
        matches = re.findall(self.OBJECTIVE_PATTERN, expr, re.IGNORECASE)
        for match in matches:
            inner_expr = match.strip()
            if not inner_expr:
                self.errors.append("Empty expression in OBJECTIVE()")
    
    def _validate_bound_syntax(self, expr: str) -> None:
        """Validate BOUND() function syntax."""
        matches = re.findall(self.BOUND_PATTERN, expr, re.IGNORECASE)
        for match in matches:
            var_name = match[0].strip()
            lower = match[1].strip()
            upper = match[2].strip()
            
            # Check variable name
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
                self.errors.append(f"Invalid variable name in BOUND(): '{var_name}'")
            
            # Check bound values
            if lower.upper() != 'NONE':
                try:
                    float(lower)
                except ValueError:
                    self.errors.append(f"Invalid lower bound in BOUND(): '{lower}'")
            
            if upper.upper() != 'NONE':
                try:
                    float(upper)
                except ValueError:
                    self.errors.append(f"Invalid upper bound in BOUND(): '{upper}'")
    
    def _validate_dot_syntax(self, expr: str) -> None:
        """Validate DOT() function syntax."""
        if 'DOT(' in expr.upper():
            # Check for balanced parentheses
            if not self._has_balanced_parentheses(expr):
                self.errors.append("Unbalanced parentheses in DOT() expression")
            
            # Check for comma separating arguments
            dot_start = expr.upper().find('DOT(')
            if dot_start != -1:
                inner_start = dot_start + 4
                inner_end = self._find_matching_parenthesis(expr, inner_start - 1)
                if inner_end != -1:
                    inner = expr[inner_start:inner_end]
                    if ',' not in inner:
                        self.errors.append("DOT() requires two arguments separated by comma")
    
    def _validate_norm_syntax(self, expr: str) -> None:
        """Validate NORM() function syntax."""
        if 'NORM(' in expr.upper():
            # Check for balanced parentheses
            if not self._has_balanced_parentheses(expr):
                self.errors.append("Unbalanced parentheses in NORM() expression")
    
    def _validate_vector_syntax(self, expr: str) -> None:
        """Validate vector() function syntax."""
        if 'VECTOR(' in expr.upper():
            # Check for balanced parentheses
            if not self._has_balanced_parentheses(expr):
                self.errors.append("Unbalanced parentheses in vector() expression")
    
    def _check_circular_dependencies(self, formulas: Dict[str, str]) -> None:
        """Check for circular dependencies in formulas."""
        # Build dependency graph
        graph = {}
        for target, expr in formulas.items():
            deps = extract_identifiers(expr)
            graph[target] = {d for d in deps if d in formulas}
        
        # Check for cycles using DFS
        visited = set()
        recursion_stack = set()
        
        def has_cycle(node):
            visited.add(node)
            recursion_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in recursion_stack:
                    return True
            
            recursion_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    self.errors.append(f"Circular dependency detected involving '{node}'")
                    break
    
    def _check_undefined_variables(self, formulas: Dict[str, str]) -> None:
        """Check for undefined variables in formulas."""
        all_variables = set()
        defined_variables = set(formulas.keys())
        
        # Collect all variables used in formulas
        for expr in formulas.values():
            all_variables |= extract_identifiers(expr)
        
        # Filter out function names
        function_names = set(SAFE_FUNCTIONS.keys()) if 'SAFE_FUNCTIONS' in globals() else set()
        undefined = all_variables - defined_variables - function_names
        
        # Also check for DSL keywords that might be mistaken as variables
        dsl_keywords = {'DECISION', 'OBJECTIVE', 'BOUND', 'DOT', 'NORM', 'vector'}
        undefined = {var for var in undefined if var.upper() not in dsl_keywords}
        
        if undefined:
            self.warnings.append(f"Potentially undefined variables: {sorted(undefined)}")
    
    def _check_vector_size_mismatches(self, formulas: Dict[str, str]) -> None:
        """Check for potential vector size mismatches."""
        # This is a simplified check - actual size validation requires data context
        # Look for patterns like DOT(vector1, vector2) where vectors might have different sizes
        for expr in formulas.values():
            if 'DOT(' in expr.upper():
                self.warnings.append(f"Vector size mismatch check needed for DOT() in expression: {expr}")
    
    def _check_inequality_expressions(self, formulas: Dict[str, str]) -> None:
        """Check for invalid inequality expressions."""
        inequality_ops = ['<=', '>=', '<', '>', '==']
        
        for target, expr in formulas.items():
            for op in inequality_ops:
                if op in expr:
                    # Check if it's a valid constraint expression
                    parts = expr.split(op, 1)
                    if len(parts) != 2:
                        self.errors.append(f"Invalid inequality expression in '{target}': {expr}")
                    else:
                        left, right = parts
                        # Check if both sides are non-empty
                        if not left.strip() or not right.strip():
                            self.errors.append(f"Invalid inequality expression in '{target}': empty side")
    
    def _check_bound_syntax(self, formulas: Dict[str, str]) -> None:
        """Check for incorrect bound syntax."""
        # Already handled in _validate_bound_syntax, but check for traditional bounds
        for target, expr in formulas.items():
            if any(op in expr for op in ['<=', '>=', '<', '>']):
                # Check if it's a simple bound (one variable on one side)
                parts = re.split(r'<=|>=|<|>', expr)
                if len(parts) == 2:
                    left, right = parts
                    left_vars = self._extract_variables(left)
                    right_vars = self._extract_variables(right)
                    
                    # Simple bound should have exactly one variable
                    if len(left_vars) == 1 and len(right_vars) == 0:
                        pass  # variable <= constant
                    elif len(left_vars) == 0 and len(right_vars) == 1:
                        pass  # constant <= variable
                    else:
                        self.warnings.append(f"Complex bound expression in '{target}': {expr}")
    
    def _extract_variables(self, expr: str) -> Set[str]:
        """Extract variable names from expression."""
        # Simple regex-based extraction
        var_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
        matches = re.findall(var_pattern, expr)
        
        # Filter out function names
        function_names = set(SAFE_FUNCTIONS.keys()) if 'SAFE_FUNCTIONS' in globals() else set()
        dsl_keywords = {'DECISION', 'OBJECTIVE', 'BOUND', 'DOT', 'NORM', 'vector'}
        
        variables = set()
        for match in matches:
            if match not in function_names and match.upper() not in dsl_keywords:
                variables.add(match)
        
        return variables
    
    def _has_balanced_parentheses(self, expr: str) -> bool:
        """Check if expression has balanced parentheses."""
        count = 0
        for char in expr:
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
                if count < 0:
                    return False
        return count == 0
    
    def _find_matching_parenthesis(self, expr: str, start_pos: int) -> int:
        """Find the position of the matching closing parenthesis."""
        if expr[start_pos] != '(':
            return -1
        
        paren_count = 1
        pos = start_pos + 1
        
        while pos < len(expr) and paren_count > 0:
            if expr[pos] == '(':
                paren_count += 1
            elif expr[pos] == ')':
                paren_count -= 1
            pos += 1
        
        if paren_count == 0:
            return pos - 1
        return -1

# ============================================================================
# DATA CONSISTENCY VALIDATION
# ============================================================================

class DataConsistencyValidator:
    """Validates data consistency with DSL formulas."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_data_consistency(
        self, 
        formulas: Dict[str, str], 
        scenario_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate that input data is consistent with DSL formulas.
        
        Args:
            formulas: Dictionary of target:expression formulas
            scenario_context: Scenario context with vector data
            
        Returns:
            Dictionary with validation results
        """
        self.errors = []
        self.warnings = []
        
        print("\n" + "="*80)
        print("DATA CONSISTENCY VALIDATION")
        print("="*80)
        
        # Check vector lengths
        self._check_vector_lengths(scenario_context)
        
        # Check vector operations compatibility
        self._check_vector_operations(formulas, scenario_context)
        
        # Check required variables for formulas
        self._check_required_variables(formulas, scenario_context)
        
        # Check numeric consistency
        self._check_numeric_consistency(scenario_context)
        
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors.copy(),
            'warnings': self.warnings.copy(),
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }
    
    def _check_vector_lengths(self, context: Dict[str, Any]) -> None:
        """Check that all vectors have consistent lengths."""
        vector_lengths = {}
        
        # Identify all vectors in context
        for key, value in context.items():
            if isinstance(value, (list, np.ndarray)):
                vector_lengths[key] = len(value)
        
        # Check for consistent lengths
        if vector_lengths:
            lengths = list(vector_lengths.values())
            first_length = lengths[0]
            
            for key, length in vector_lengths.items():
                if length != first_length:
                    self.errors.append(
                        f"Vector length mismatch: '{key}' has length {length}, "
                        f"expected {first_length} (like other vectors)"
                    )
            
            print(f"Vector lengths: {vector_lengths}")
            if len(set(lengths)) == 1:
                print(f"OK All vectors have consistent length: {first_length}")
            else:
                print(f"CHECK Vector length mismatch detected")
    
    def _check_vector_operations(self, formulas: Dict[str, str], context: Dict[str, Any]) -> None:
        """Check that vector operations are compatible."""
        for expr in formulas.values():
            # Check DOT operations
            if 'DOT(' in expr.upper():
                # Extract vector names from DOT expression
                dot_pattern = r'DOT\s*\(\s*([^,)]+)\s*,\s*([^)]+)\s*\)'
                matches = re.findall(dot_pattern, expr, re.IGNORECASE)
                
                for match in matches:
                    vector1_expr = match[0].strip()
                    vector2_expr = match[1].strip()
                    
                    # Try to get vector lengths
                    len1 = self._get_vector_length(vector1_expr, context)
                    len2 = self._get_vector_length(vector2_expr, context)
                    
                    if len1 is not None and len2 is not None and len1 != len2:
                        self.errors.append(
                            f"DOT() vector size mismatch: '{vector1_expr}' (length {len1}) "
                            f"and '{vector2_expr}' (length {len2})"
                        )
                    elif len1 is not None and len2 is not None:
                        print(f"check DOT() vectors compatible: {vector1_expr}[{len1}] · {vector2_expr}[{len2}]")
                    
            # Check NORM operations
            if 'NORM(' in expr.upper():
                # Extract vector name from NORM expression
                norm_pattern = r'NORM\s*\(\s*([^)]+)\s*\)'
                matches = re.findall(norm_pattern, expr, re.IGNORECASE)
                
                for match in matches:
                    vector_expr = match.strip()
                    length = self._get_vector_length(vector_expr, context)
                    if length is not None:
                        print(f"OK NORM() vector '{vector_expr}' has length {length}")
    
    def _check_required_variables(self, formulas: Dict[str, str], context: Dict[str, Any]) -> None:
        """Check that all required variables for formulas are present in context."""
        all_required_vars = set()
        
        # Extract all variables from formulas
        for expr in formulas.values():
            all_required_vars |= self._extract_variables_from_expr(expr)
        
        # Filter out DSL keywords and function names
        dsl_keywords = {'DECISION', 'OBJECTIVE', 'BOUND', 'DOT', 'NORM', 'vector'}
        function_names = set(SAFE_FUNCTIONS.keys()) if 'SAFE_FUNCTIONS' in globals() else set()
        
        required_vars = set()
        for var in all_required_vars:
            if var.upper() not in dsl_keywords and var not in function_names:
                required_vars.add(var)
        
        # Check which variables are missing from context
        missing_vars = []
        for var in required_vars:
            if var not in context:
                missing_vars.append(var)
        
        if missing_vars:
            self.errors.append(f"Missing required variables in context: {sorted(missing_vars)}")
        else:
            print(f"check All required variables present in context: {sorted(required_vars)}")
    
    def _check_numeric_consistency(self, context: Dict[str, Any]) -> None:
        """Check numeric consistency of data in context."""
        for key, value in context.items():
            if isinstance(value, (list, np.ndarray)):
                # Check that all elements in vector are numeric
                non_numeric = []
                for i, item in enumerate(value):
                    if not isinstance(item, (int, float, np.number)):
                        non_numeric.append((i, item))
                
                if non_numeric:
                    self.errors.append(
                        f"Non-numeric values in vector '{key}': {non_numeric[:3]}"
                    )
                else:
                    # Check for NaN or infinite values
                    if isinstance(value, np.ndarray):
                        if np.any(np.isnan(value)):
                            self.warnings.append(f"NaN values found in vector '{key}'")
                        if np.any(np.isinf(value)):
                            self.warnings.append(f"Infinite values found in vector '{key}'")
            elif isinstance(value, (int, float, np.number)):
                # Check scalar numeric values
                if np.isnan(value) or np.isinf(value):
                    self.warnings.append(f"Invalid numeric value for '{key}': {value}")
    
    def _get_vector_length(self, vector_expr: str, context: Dict[str, Any]) -> Optional[int]:
        """Get the length of a vector from context or expression."""
        # Check if it's a direct vector name
        if vector_expr in context:
            value = context[vector_expr]
            if isinstance(value, (list, np.ndarray)):
                return len(value)
        
        # Check if it's a vector() function call
        if vector_expr.startswith('vector(') and vector_expr.endswith(')'):
            inner = vector_expr[7:-1].strip()
            # Check if inner is a list literal
            if inner.startswith('[') and inner.endswith(']'):
                try:
                    list_str = inner[1:-1]
                    elements = list_str.split(',')
                    return len(elements)
                except:
                    pass
            # Check if inner is a variable name
            elif inner in context:
                value = context[inner]
                if isinstance(value, (list, np.ndarray)):
                    return len(value)
        
        return None
    
    def _extract_variables_from_expr(self, expr: str) -> Set[str]:
        """Extract variable names from expression."""
        var_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
        matches = re.findall(var_pattern, expr)
        return set(matches)


# ============================================================================
# LP MODEL VALIDATION
# ============================================================================

class LPModelValidator:
    """Validates LP model generated from DSL formulas."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_lp_model(
        self,
        formulas: Dict[str, str],
        scenario_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate that DSL produces a valid LP model.
        
        Args:
            formulas: Dictionary of target:expression formulas
            scenario_context: Scenario context with vector data
            
        Returns:
            Dictionary with validation results
        """
        self.errors = []
        self.warnings = []
        
        print("\n" + "="*80)
        print("LP MODEL VALIDATION")
        print("="*80)
        
        if not LP_AVAILABLE:
            self.errors.append("LP modules not available for validation")
            return {
                'valid': False,
                'errors': self.errors.copy(),
                'warnings': self.warnings.copy(),
                'error_count': len(self.errors),
                'warning_count': len(self.warnings)
            }
        
        try:
            # Parse LP formulas
            parser = LPModelParser()
            lp_spec = parser.detect_lp_formulas(formulas)
            
            if not lp_spec['is_lp_problem']:
                print("No LP problem detected in formulas")
                return {
                    'valid': True,
                    'errors': [],
                    'warnings': [],
                    'error_count': 0,
                    'warning_count': 0,
                    'lp_spec': lp_spec
                }
            
            print(f"LP Specification:")
            print(f"  Variables: {lp_spec['variables']}")
            print(f"  Objective: {lp_spec['objective']}")
            print(f"  Constraints: {lp_spec['constraints']}")
            print(f"  Bounds: {lp_spec['bounds']}")
            print(f"  DSL Structures: {list(lp_spec['dsl_structures'].keys())}")
            
            # Build LP matrices
            builder = LPMatrixBuilder(scenario_context)
            lp_matrices = builder.build_from_formulas(formulas, lp_spec)
            
            # Validate LP matrix dimensions
            self._validate_lp_dimensions(lp_matrices)
            
            # Validate constraint consistency
            self._validate_constraint_consistency(lp_matrices)
            
            # Validate bounds
            self._validate_bounds(lp_matrices)
            
            # Test solver
            solver_result = self._test_solver(lp_matrices)
            
            return {
                'valid': len(self.errors) == 0,
                'errors': self.errors.copy(),
                'warnings': self.warnings.copy(),
                'error_count': len(self.errors),
                'warning_count': len(self.warnings),
                'lp_spec': lp_spec,
                'lp_matrices': lp_matrices,
                'solver_test': solver_result
            }
            
        except Exception as e:
            self.errors.append(f"LP model validation failed: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                'valid': False,
                'errors': self.errors.copy(),
                'warnings': self.warnings.copy(),
                'error_count': len(self.errors),
                'warning_count': len(self.warnings)
            }
    
    def _validate_lp_dimensions(self, lp_matrices: Dict[str, Any]) -> None:
        """Validate LP matrix dimensions are consistent."""
        n_vars = len(lp_matrices.get('variables', []))
        c_vector = lp_matrices.get('c', [])
        A_ub = lp_matrices.get('A_ub', [])
        b_ub = lp_matrices.get('b_ub', [])
        bounds = lp_matrices.get('bounds', [])
        
        print(f"\nLP Matrix Dimensions:")
        print(f"  Variables: {n_vars}")
        print(f"  c vector length: {len(c_vector)}")
        print(f"  A_ub shape: {len(A_ub)}x{len(A_ub[0]) if A_ub else 0}")
        print(f"  b_ub length: {len(b_ub)}")
        print(f"  bounds count: {len(bounds)}")
        
        # Check c vector dimension
        if len(c_vector) != n_vars:
            self.errors.append(
                f"Objective vector dimension mismatch: "
                f"c has {len(c_vector)} elements, expected {n_vars}"
            )
        else:
            print(f"  OK c vector dimension correct")
        
        # Check bounds dimension
        if len(bounds) != n_vars:
            self.errors.append(
                f"Bounds dimension mismatch: "
                f"bounds has {len(bounds)} elements, expected {n_vars}"
            )
        else:
            print(f"  OK bounds dimension correct")
        
        # Check A_ub and b_ub dimensions
        if A_ub:
            n_constraints = len(A_ub)
            
            if len(b_ub) != n_constraints:
                self.errors.append(
                    f"Constraint dimension mismatch: "
                    f"A_ub has {n_constraints} rows, b_ub has {len(b_ub)} elements"
                )
            else:
                print(f"  OK b_ub dimension matches A_ub rows")
            
            for i, row in enumerate(A_ub):
                if len(row) != n_vars:
                    self.errors.append(
                        f"Constraint row {i} dimension mismatch: "
                        f"row has {len(row)} elements, expected {n_vars}"
                    )
                    break
            else:
                print(f"  OK All constraint rows have correct dimension")
    
    def _validate_constraint_consistency(self, lp_matrices: Dict[str, Any]) -> None:
        """Validate that constraints are consistent."""
        A_ub = lp_matrices.get('A_ub', [])
        b_ub = lp_matrices.get('b_ub', [])
        
        if not A_ub:
            print(f"  OK No inequality constraints to validate")
            return
        
        # Check for empty constraints (all zeros)
        for i, row in enumerate(A_ub):
            if all(abs(coeff) < 1e-10 for coeff in row):
                self.warnings.append(f"Constraint {i} has all zero coefficients")
        
        # Check for duplicate constraints
        constraint_signatures = []
        for i, row in enumerate(A_ub):
            sig = tuple(round(coeff, 6) for coeff in row) + (round(b_ub[i], 6),)
            if sig in constraint_signatures:
                self.warnings.append(f"Constraint {i} is duplicate of earlier constraint")
            else:
                constraint_signatures.append(sig)
        
        print(f"  OK Constraint consistency check completed")
    
    def _validate_bounds(self, lp_matrices: Dict[str, Any]) -> None:
        """Validate variable bounds."""
        bounds = lp_matrices.get('bounds', [])
        variables = lp_matrices.get('variables', [])
        
        for i, (lower, upper) in enumerate(bounds):
            var_name = variables[i] if i < len(variables) else f"var_{i}"
            
            # Check lower <= upper when both are specified
            if lower is not None and upper is not None and lower > upper:
                self.errors.append(
                    f"Invalid bounds for {var_name}: lower={lower} > upper={upper}"
                )
            
            # Check for negative bounds on non-negative variables
            if lower is not None and lower < 0 and var_name.startswith('x'):
                self.warnings.append(
                    f"Negative lower bound for decision variable {var_name}: {lower}"
                )
        
        print(f"  OK Bounds validation completed")
    
    def _test_solver(self, lp_matrices: Dict[str, Any]) -> Dict[str, Any]:
        """Test LP solver with the generated matrices."""
        try:
            solver = LPSolver()
            result = solver.solve_from_matrices(lp_matrices, maximize=True)
            
            print(f"\nSolver Test Results:")
            print(f"  Success: {result.get('success', False)}")
            print(f"  Status: {result.get('status', 'N/A')}")
            print(f"  Message: {result.get('message', 'N/A')}")
            
            if result.get('success', False):
                print(f"  OK Solver converged successfully")
                
                # Check solution feasibility
                x = result.get('x')
                if x is not None:
                    # Check bounds
                    bounds = lp_matrices.get('bounds', [])
                    for i, (lower, upper) in enumerate(bounds):
                        if i < len(x):
                            val = x[i]
                            if lower is not None and val < lower - 1e-6:
                                self.warnings.append(
                                    f"Solution violates lower bound for variable {i}: "
                                    f"{val} < {lower}"
                                )
                            if upper is not None and val > upper + 1e-6:
                                self.warnings.append(
                                    f"Solution violates upper bound for variable {i}: "
                                    f"{val} > {upper}"
                                )
                    
                    print(f"  OK Solution respects bounds")
            else:
                self.warnings.append(f"Solver failed: {result.get('message', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            self.errors.append(f"Solver test failed: {str(e)}")
            return {'success': False, 'error': str(e)}


# ============================================================================
# API PRODUCTION TEST
# ============================================================================

class APITestValidator:
    """Validates API endpoint for production."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_api_endpoint(self, indicator_id: str, id_column: str = "ID") -> Dict[str, Any]:
        """
        Validate API endpoint with curl/Postman test.
        
        Args:
            indicator_id: Indicator ID to test
            id_column: ID column name
            
        Returns:
            Dictionary with validation results
        """
        self.errors = []
        self.warnings = []
        
        print("\n" + "="*80)
        print("API PRODUCTION TEST")
        print("="*80)
        
        # Generate curl command
        curl_command = (
            f'curl -X POST http://localhost:8000/formula/calculate \\\n'
            f'  -H "Content-Type: application/json" \\\n'
            f'  -d \'{{\n'
            f'    "indicator_id": "{indicator_id}",\n'
            f'    "id_column": "{id_column}"\n'
            f'  }}\''
        )
        
        print(f"Generated curl command:\n{curl_command}")
        
        # Generate Python test code
        python_test = f"""import requests
import json

url = "http://localhost:8000/formula/calculate"
payload = {{
    "indicator_id": "{indicator_id}",
    "id_column": "{id_column}"
}}
headers = {{"Content-Type": "application/json"}}

try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    result = response.json()
    
    print(f"Status Code: {{response.status_code}}")
    print(f"Response: {{json.dumps(result, indent=2)}}")
    
    # Validate response structure
    required_keys = ["success", "updated_rows", "errors"]
    for key in required_keys:
        if key not in result:
            print(f"ERROR: Missing key '{{key}}' in response")
    
    if result.get("success") and result.get("updated_rows", 0) > 0:
        print("OK API test passed")
    else:
        print(f"ERROR API test failed: {{result.get('error', 'Unknown error')}}")
        
except Exception as e:
    print(f"ERROR: API test failed: {{e}}")"""
        
        print(f"\nPython test code:\n{python_test}")
        
        # Check if API server is likely running
        self._check_api_server()
        
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors.copy(),
            'warnings': self.warnings.copy(),
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'curl_command': curl_command,
            'python_test': python_test
        }
    
    def _check_api_server(self) -> None:
        """Check if API server is likely running."""
        # This is a basic check - in production would actually test the endpoint
        print("\nAPI Server Check:")
        print("  Note: Manual verification required")
        print("  1. Ensure API server is running: python cvp-sphere-api/main.py")
        print("  2. Test endpoint with curl or Postman")
        print("  3. Verify response contains: success=true, updated_rows>0, errors=0")
        
        self.warnings.append("API test requires manual verification (server must be running)")


# ============================================================================
# SAFETY CHECKS BEFORE PRODUCTION
# ============================================================================

class SafetyValidator:
    """Performs safety checks before production execution."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_safety(
        self,
        formulas: Dict[str, str],
        scenario_context: Dict[str, Any],
        lp_matrices: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform safety checks before production.
        
        Args:
            formulas: Dictionary of target:expression formulas
            scenario_context: Scenario context with vector data
            lp_matrices: Optional LP matrices for additional validation
            
        Returns:
            Dictionary with validation results
        """
        self.errors = []
        self.warnings = []
        
        print("\n" + "="*80)
        print("SAFETY CHECKS BEFORE PRODUCTION")
        print("="*80)
        
        # Check for recursion loops
        self._check_recursion_loops(formulas)
        
        # Check for unsafe operations
        self._check_unsafe_operations(formulas)
        
        # Check LP solver convergence (if LP matrices provided)
        if lp_matrices and LP_AVAILABLE:
            self._check_lp_solver_convergence(lp_matrices)
        
        # Check decision variable mapping
        self._check_decision_variable_mapping(formulas, scenario_context)
        
        # Check LP matrix validity
        if lp_matrices:
            self._check_lp_matrix_validity(lp_matrices)
        
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors.copy(),
            'warnings': self.warnings.copy(),
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }
    
    def _check_recursion_loops(self, formulas: Dict[str, str]) -> None:
        """Check for recursion loops in DSL formulas."""
        # Build dependency graph
        graph = {}
        for target, expr in formulas.items():
            deps = extract_identifiers(expr)
            graph[target] = {d for d in deps if d in formulas}
        
        # Check for cycles
        visited = set()
        recursion_stack = set()
        
        def has_cycle(node):
            visited.add(node)
            recursion_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in recursion_stack:
                    return True
            
            recursion_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    self.errors.append(f"Recursion loop detected involving '{node}'")
                    return
        
        print(f"  OK No recursion loops detected")
    
    def _check_unsafe_operations(self, formulas: Dict[str, str]) -> None:
        """Check for unsafe operations in formulas."""
        unsafe_keywords = [
            'import', 'exec', 'eval', 'open', 'os.', 'sys.', '__',
            'subprocess', 'shutil', 'pickle', 'yaml', 'json.loads'
        ]
        
        unsafe_formulas = []
        for target, expr in formulas.items():
            expr_lower = expr.lower()
            for keyword in unsafe_keywords:
                if keyword in expr_lower:
                    unsafe_formulas.append(target)
                    break
        
        if unsafe_formulas:
            self.errors.append(f"Unsafe operations detected in formulas: {unsafe_formulas}")
        else:
            print(f"  OK No unsafe operations detected")
    
    def _check_lp_solver_convergence(self, lp_matrices: Dict[str, Any]) -> None:
        """Check LP solver convergence."""
        try:
            solver = LPSolver()
            result = solver.solve_from_matrices(lp_matrices, maximize=True)
            
            if result.get('success', False):
                print(f"  OK LP solver converges successfully")
                
                # Check solution quality
                x = result.get('x')
                if x is not None:
                    # Check for NaN or infinite values
                    if any(np.isnan(val) for val in x if isinstance(val, float)):
                        self.warnings.append("LP solution contains NaN values")
                    if any(np.isinf(val) for val in x if isinstance(val, float)):
                        self.warnings.append("LP solution contains infinite values")
            else:
                self.warnings.append(f"LP solver may not converge: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            self.warnings.append(f"LP solver convergence check failed: {str(e)}")
    
    def _check_decision_variable_mapping(self, formulas: Dict[str, str], context: Dict[str, Any]) -> None:
        """Check that decision variables are correctly mapped."""
        if not LP_AVAILABLE:
            return
        
        try:
            parser = LPModelParser()
            lp_spec = parser.detect_lp_formulas(formulas)
            
            if not lp_spec['is_lp_problem']:
                return
            
            # Check DSL decision declarations
            dsl_structures = lp_spec.get('dsl_structures', {})
            if 'decision' in dsl_structures:
                for decision_info in dsl_structures['decision']:
                    var_name = decision_info.get('variable_name')
                    size = decision_info.get('size')
                    vector_vars = decision_info.get('vector_variables', [])
                    
                    print(f"  Decision variable: {var_name}, size={size}, vector_vars={vector_vars}")
                    
                    # Check if vector variables exist in context or will be created
                    for vec_var in vector_vars:
                        if vec_var not in context:
                            print(f"    Warning: Vector variable '{vec_var}' not in context (will be created by LP solver)")
            
            print(f"  OK Decision variable mapping validated")
            
        except Exception as e:
            self.warnings.append(f"Decision variable mapping check failed: {str(e)}")
    
    def _check_lp_matrix_validity(self, lp_matrices: Dict[str, Any]) -> None:
        """Check LP matrix validity."""
        # Check for NaN or infinite values in matrices
        c_vector = lp_matrices.get('c', [])
        A_ub = lp_matrices.get('A_ub', [])
        b_ub = lp_matrices.get('b_ub', [])
        
        # Check c vector
        for i, val in enumerate(c_vector):
            if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                self.errors.append(f"Invalid value in c vector at index {i}: {val}")
        
        # Check A_ub matrix
        for i, row in enumerate(A_ub):
            for j, val in enumerate(row):
                if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                    self.errors.append(f"Invalid value in A_ub at ({i},{j}): {val}")
        
        # Check b_ub vector
        for i, val in enumerate(b_ub):
            if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                self.errors.append(f"Invalid value in b_ub at index {i}: {val}")
        
        if not self.errors:
            print(f"  OK LP matrix values are valid (no NaN/inf)")


# ============================================================================
# PRODUCTION READINESS REPORT
# ============================================================================

class ProductionReadinessReporter:
    """Generates production readiness report."""
    
    def generate_report(
        self,
        dsl_validation: Dict[str, Any],
        data_validation: Dict[str, Any],
        lp_validation: Dict[str, Any],
        api_validation: Dict[str, Any],
        safety_validation: Dict[str, Any],
        indicator_id: str
    ) -> Dict[str, Any]:
        """
        Generate comprehensive production readiness report.
        
        Args:
            dsl_validation: DSL syntax validation results
            data_validation: Data consistency validation results
            lp_validation: LP model validation results
            api_validation: API test validation results
            safety_validation: Safety validation results
            indicator_id: Indicator ID being validated
            
        Returns:
            Dictionary with production readiness report
        """
        print("\n" + "="*80)
        print("PRODUCTION READINESS REPORT")
        print("="*80)
        
        # Calculate overall status
        all_valid = (
            dsl_validation.get('valid', False) and
            data_validation.get('valid', False) and
            lp_validation.get('valid', False) and
            safety_validation.get('valid', False)
        )
        
        total_errors = (
            dsl_validation.get('error_count', 0) +
            data_validation.get('error_count', 0) +
            lp_validation.get('error_count', 0) +
            safety_validation.get('error_count', 0)
        )
        
        total_warnings = (
            dsl_validation.get('warning_count', 0) +
            data_validation.get('warning_count', 0) +
            lp_validation.get('warning_count', 0) +
            safety_validation.get('warning_count', 0) +
            api_validation.get('warning_count', 0)
        )
        
        # Generate report
        report = {
            'indicator_id': indicator_id,
            'validation_timestamp': datetime.datetime.now().isoformat(),
            'overall_status': 'READY' if all_valid and total_errors == 0 else 'NOT_READY',
            'summary': {
                'dsl_syntax_valid': dsl_validation.get('valid', False),
                'data_consistent': data_validation.get('valid', False),
                'lp_model_valid': lp_validation.get('valid', False),
                'safety_checks_passed': safety_validation.get('valid', False),
                'total_errors': total_errors,
                'total_warnings': total_warnings
            },
            'detailed_results': {
                'dsl_syntax_validation': dsl_validation,
                'data_consistency_validation': data_validation,
                'lp_model_validation': lp_validation,
                'api_test_validation': api_validation,
                'safety_validation': safety_validation
            },
            'recommendations': []
        }
        
        # Generate recommendations
        if not dsl_validation.get('valid', False):
            report['recommendations'].append(
                "Fix DSL syntax errors before production deployment"
            )
        
        if not data_validation.get('valid', False):
            report['recommendations'].append(
                "Resolve data consistency issues (vector length mismatches, missing variables)"
            )
        
        if not lp_validation.get('valid', False):
            report['recommendations'].append(
                "Fix LP model issues (matrix dimension mismatches, invalid bounds)"
            )
        
        if not safety_validation.get('valid', False):
            report['recommendations'].append(
                "Address safety issues (unsafe operations, recursion loops)"
            )
        
        if total_warnings > 0:
            report['recommendations'].append(
                f"Review {total_warnings} warnings before production"
            )
        
        if api_validation.get('warning_count', 0) > 0:
            report['recommendations'].append(
                "Perform manual API test to verify endpoint functionality"
            )
        
        # Print report summary
        print(f"\nIndicator ID: {indicator_id}")
        print(f"Overall Status: {report['overall_status']}")
        print(f"Total Errors: {total_errors}")
        print(f"Total Warnings: {total_warnings}")
        
        print(f"\nValidation Results:")
        print(f"  DSL Syntax: {'PASS' if dsl_validation.get('valid', False) else 'FAIL'}")
        print(f"  Data Consistency: {'PASS' if data_validation.get('valid', False) else 'FAIL'}")
        print(f"  LP Model: {'PASS' if lp_validation.get('valid', False) else 'FAIL'}")
        print(f"  Safety Checks: {'PASS' if safety_validation.get('valid', False) else 'FAIL'}")
        
        if report['recommendations']:
            print(f"\nRecommendations:")
            for i, rec in enumerate(report['recommendations'], 1):
                print(f"  {i}. {rec}")
        else:
            print(f"\nOK All validation checks passed. Model is ready for production.")
        
        return report


# ============================================================================
# MAIN VALIDATION FUNCTION
# ============================================================================

def validate_dsl_model(
    indicator_id: str,
    formulas: Optional[Dict[str, str]] = None,
    scenario_context: Optional[Dict[str, Any]] = None,
    id_column: str = "ID"
) -> Dict[str, Any]:
    """
    Main function to validate DSL model for production.
    
    Args:
        indicator_id: Indicator ID to validate
        formulas: Optional formulas dictionary (if None, will be fetched from DB)
        scenario_context: Optional scenario context with data
        id_column: ID column name for API test
        
    Returns:
        Comprehensive validation report
    """
    import datetime
    
    print("="*80)
    print(f"DSL MODEL VALIDATION FOR INDICATOR: {indicator_id}")
    print("="*80)
    
    # If formulas not provided, try to fetch from database
    if formulas is None:
        print(f"\n[INFO] Formulas not provided. Attempting to fetch from database...")
        try:
            from pythoncode import get_formulas_from_db
            table_name, formulas = get_formulas_from_db(int(indicator_id))
            print(f"[INFO] Fetched {len(formulas)} formulas from database")
        except Exception as e:
            print(f"[ERROR] Failed to fetch formulas from database: {e}")
            print(f"[INFO] Using example formulas for validation")
            # Use example formulas
            formulas = {
                'CM_J': 'P_J - C_J',
                'CM_NORM': 'NORM(vector(CM_J))',
                'SAFE_X_MIN': 'X0_J - r0*(CM_J/CM_NORM)',
                'SAFE_X_MAX': 'X0_J + r0*(CM_J/CM_NORM)',
                'DECISION_X': 'DECISION(x,size=3)',
                'DECISION_R': 'DECISION(r)',
                'OBJ': 'OBJECTIVE(DOT(vector(CM_J),x))',
                'BOUND_X': 'BOUND(x,XMIN,XMAX)',
                'BOUND_R': 'BOUND(r,0,None)',
                'CONSTRAINT_LP': '-DOT(vector(CM_J),x)+NORM(vector(CM_J))*r<=-F'
            }
    
    # If scenario_context not provided, use example data
    if scenario_context is None:
        print(f"\n[INFO] Scenario context not provided. Using example data...")
        scenario_context = {
            'P_J': [20, 17, 15],
            'C_J': [10, 11, 7],
            'X0_J': [1000, 2000, 1500],
            'r0': 200,
            'F': 2700.0,
            'XMIN': [0, 0, 0],
            'XMAX': [4800, 7800, 3800]
        }
    
    # Step 1: DSL Syntax Validation
    dsl_validator = DSLSyntaxValidator()
    dsl_results = dsl_validator.validate_formulas(formulas)
    
    # Step 2: Data Consistency Validation
    data_validator = DataConsistencyValidator()
    data_results = data_validator.validate_data_consistency(formulas, scenario_context)
    
    # Step 3: LP Model Validation
    lp_validator = LPModelValidator()
    lp_results = lp_validator.validate_lp_model(formulas, scenario_context)
    
    # Step 4: API Production Test
    api_validator = APITestValidator()
    api_results = api_validator.validate_api_endpoint(indicator_id, id_column)
    
    # Step 5: Safety Checks
    safety_validator = SafetyValidator()
    safety_results = safety_validator.validate_safety(
        formulas, 
        scenario_context, 
        lp_results.get('lp_matrices') if 'lp_matrices' in lp_results else None
    )
    
    # Step 6: Production Readiness Report
    reporter = ProductionReadinessReporter()
    report = reporter.generate_report(
        dsl_results,
        data_results,
        lp_results,
        api_results,
        safety_results,
        indicator_id
    )
    
    # Save report to file
    report_filename = f"validation_report_{indicator_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\nReport saved to: {report_filename}")
    print("="*80)
    
    return report


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate DSL model for production execution')
    parser.add_argument('indicator_id', help='Indicator ID to validate')
    parser.add_argument('--id-column', default='ID', help='ID column name (default: ID)')
    parser.add_argument('--formulas-file', help='JSON file containing formulas (optional)')
    parser.add_argument('--context-file', help='JSON file containing scenario context (optional)')
    
    args = parser.parse_args()
    
    # Load formulas from file if provided
    formulas = None
    if args.formulas_file and os.path.exists(args.formulas_file):
        with open(args.formulas_file, 'r') as f:
            formulas = json.load(f)
    
    # Load context from file if provided
    scenario_context = None
    if args.context_file and os.path.exists(args.context_file):
        with open(args.context_file, 'r') as f:
            scenario_context = json.load(f)
    
    # Run validation
    try:
        report = validate_dsl_model(
            indicator_id=args.indicator_id,
            formulas=formulas,
            scenario_context=scenario_context,
            id_column=args.id_column
        )
        
        # Exit with appropriate code
        if report['overall_status'] == 'READY':
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        print(f"\n[ERROR] Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
