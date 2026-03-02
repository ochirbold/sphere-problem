"""
lp_solver.py - Linear Programming Solver for CVP Formula Engine

This module provides a wrapper for scipy.optimize.linprog with proper
error handling and result formatting for the CVP formula engine.

Responsibilities:
1. Solve LP problems using scipy.optimize.linprog
2. Handle solver configuration and options
3. Format results for integration with scenario context
4. Provide error handling and fallback behavior
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
import warnings


# ============================================================================
# TYPE ALIASES
# ============================================================================

Vector = Union[List[float], np.ndarray]
Matrix = Union[List[List[float]], np.ndarray]
Bounds = List[Tuple[Optional[float], Optional[float]]]


# ============================================================================
# LP SOLVER
# ============================================================================

class LPSolver:
    """
    Solves linear programming problems using scipy.optimize.linprog.
    
    This class provides a consistent interface for solving LP problems
    with proper error handling and result formatting.
    
    Attributes:
        method: Solver method to use (default: 'highs')
        options: Solver options dictionary
        tolerance: Numerical tolerance for constraints
    """
    
    def __init__(
        self,
        method: str = 'highs',
        options: Optional[Dict[str, Any]] = None,
        tolerance: float = 1e-8
    ):
        """
        Initialize the LP solver.
        
        Args:
            method: Solver method ('highs', 'highs-ds', 'highs-ipm', 'simplex', 'revised simplex')
            options: Solver options dictionary
            tolerance: Numerical tolerance for constraint satisfaction
        """
        self.method = method
        self.options = options or {}
        self.tolerance = tolerance
        
        # Set default options if not provided
        if 'tol' not in self.options:
            self.options['tol'] = 1e-9
        if 'maxiter' not in self.options:
            self.options['maxiter'] = 10000
    
    def solve(
        self,
        c: Vector,
        A_ub: Optional[Matrix] = None,
        b_ub: Optional[Vector] = None,
        A_eq: Optional[Matrix] = None,
        b_eq: Optional[Vector] = None,
        bounds: Optional[Bounds] = None,
        maximize: bool = False
    ) -> Dict[str, Any]:
        """
        Solve a linear programming problem.
        
        Args:
            c: Linear objective function coefficients
            A_ub: Inequality constraint matrix (A_ub * x <= b_ub)
            b_ub: Inequality constraint vector
            A_eq: Equality constraint matrix (A_eq * x == b_eq)
            b_eq: Equality constraint vector
            bounds: Sequence of (min, max) pairs for each variable
            maximize: If True, maximize the objective; if False, minimize
            
        Returns:
            Dictionary containing solution results:
                - success: Boolean indicating if optimization succeeded
                - x: Optimal solution vector (list)
                - fun: Optimal objective function value
                - message: Status message from solver
                - status: Numerical status code
                - iterations: Number of iterations performed
                - slack: Slack variables for inequality constraints
                - con: Residuals for equality constraints
                - solver_info: Additional solver information
                
        Raises:
            ImportError: If scipy is not installed
            ValueError: If problem dimensions are inconsistent
        """
        try:
            from scipy.optimize import linprog
        except ImportError:
            raise ImportError(
                "Linear programming requires scipy library. "
                "Install with: pip install scipy"
            )
        
        # Convert inputs to numpy arrays
        c_arr = np.asarray(c, dtype=float)
        
        # If maximizing, negate the objective coefficients (linprog minimizes)
        if maximize:
            c_arr = -c_arr
        
        A_ub_arr = np.asarray(A_ub, dtype=float) if A_ub is not None else None
        b_ub_arr = np.asarray(b_ub, dtype=float) if b_ub is not None else None
        A_eq_arr = np.asarray(A_eq, dtype=float) if A_eq is not None else None
        b_eq_arr = np.asarray(b_eq, dtype=float) if b_eq is not None else None
        
        # Validate dimensions
        self._validate_problem_dimensions(
            c_arr, A_ub_arr, b_ub_arr, A_eq_arr, b_eq_arr, bounds
        )
        
        # Solve the linear programming problem
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = linprog(
                c=c_arr,
                A_ub=A_ub_arr,
                b_ub=b_ub_arr,
                A_eq=A_eq_arr,
                b_eq=b_eq_arr,
                bounds=bounds,
                method=self.method,
                options=self.options
            )
        
        # Format the result
        return self._format_result(result, maximize)
    
    def solve_from_matrices(
        self,
        lp_matrices: Dict[str, Any],
        maximize: bool = False
    ) -> Dict[str, Any]:
        """
        Solve LP problem from pre-built matrices.
        
        Args:
            lp_matrices: Dictionary containing LP matrices:
                - c: Objective coefficients
                - A_ub: Inequality constraint matrix (optional)
                - b_ub: Inequality constraint vector (optional)
                - A_eq: Equality constraint matrix (optional)
                - b_eq: Equality constraint vector (optional)
                - bounds: Variable bounds (optional)
            maximize: If True, maximize the objective; if False, minimize
            
        Returns:
            Dictionary containing solution results
        """
        return self.solve(
            c=lp_matrices['c'],
            A_ub=lp_matrices.get('A_ub'),
            b_ub=lp_matrices.get('b_ub'),
            A_eq=lp_matrices.get('A_eq'),
            b_eq=lp_matrices.get('b_eq'),
            bounds=lp_matrices.get('bounds'),
            maximize=maximize
        )
    
    def _validate_problem_dimensions(
        self,
        c: np.ndarray,
        A_ub: Optional[np.ndarray],
        b_ub: Optional[np.ndarray],
        A_eq: Optional[np.ndarray],
        b_eq: Optional[np.ndarray],
        bounds: Optional[Bounds]
    ) -> None:
        """
        Validate that all problem dimensions are consistent.
        
        Args:
            c: Objective coefficients
            A_ub: Inequality constraint matrix
            b_ub: Inequality constraint vector
            A_eq: Equality constraint matrix
            b_eq: Equality constraint vector
            bounds: Variable bounds
            
        Raises:
            ValueError: If dimensions are inconsistent
        """
        n_vars = len(c)
        
        # Validate bounds
        if bounds is not None:
            if len(bounds) != n_vars:
                raise ValueError(
                    f"Bounds dimension mismatch: "
                    f"bounds has {len(bounds)} elements, expected {n_vars}"
                )
        
        # Validate inequality constraints
        if A_ub is not None and b_ub is not None:
            if A_ub.shape[0] != len(b_ub):
                raise ValueError(
                    f"Inequality constraint dimension mismatch: "
                    f"A_ub has {A_ub.shape[0]} rows, b_ub has {len(b_ub)} elements"
                )
            if A_ub.shape[1] != n_vars:
                raise ValueError(
                    f"Inequality constraint variable mismatch: "
                    f"A_ub has {A_ub.shape[1]} columns, expected {n_vars}"
                )
        
        # Validate equality constraints
        if A_eq is not None and b_eq is not None:
            if A_eq.shape[0] != len(b_eq):
                raise ValueError(
                    f"Equality constraint dimension mismatch: "
                    f"A_eq has {A_eq.shape[0]} rows, b_eq has {len(b_eq)} elements"
                )
            if A_eq.shape[1] != n_vars:
                raise ValueError(
                    f"Equality constraint variable mismatch: "
                    f"A_eq has {A_eq.shape[1]} columns, expected {n_vars}"
                )
    
    def _format_result(
        self,
        result: Any,
        maximize: bool
    ) -> Dict[str, Any]:
        """
        Format scipy linprog result for CVP formula engine.
        
        Args:
            result: Result object from scipy.optimize.linprog
            maximize: Whether the original problem was a maximization
            
        Returns:
            Formatted result dictionary
        """
        # Adjust objective value if we were maximizing
        objective_value = result.fun
        if maximize and objective_value is not None:
            objective_value = -objective_value
        
        # Convert arrays to lists for JSON serialization
        x_list = result.x.tolist() if result.x is not None else None
        slack_list = result.slack.tolist() if result.slack is not None else None
        con_list = result.con.tolist() if result.con is not None else None
        
        # Extract solver information
        solver_info = {}
        if hasattr(result, 'nit'):
            solver_info['iterations'] = result.nit
        if hasattr(result, 'status'):
            solver_info['status_code'] = result.status
        if hasattr(result, 'message'):
            solver_info['message'] = str(result.message)
        
        return {
            'success': bool(result.success),
            'x': x_list,
            'fun': objective_value,
            'message': str(result.message) if result.message else '',
            'status': int(result.status) if hasattr(result, 'status') else -1,
            'iterations': int(result.nit) if hasattr(result, 'nit') else 0,
            'slack': slack_list,
            'con': con_list,
            'solver_info': solver_info
        }
    
    def check_feasibility(
        self,
        x: Vector,
        A_ub: Optional[Matrix] = None,
        b_ub: Optional[Vector] = None,
        A_eq: Optional[Matrix] = None,
        b_eq: Optional[Vector] = None,
        bounds: Optional[Bounds] = None
    ) -> Dict[str, Any]:
        """
        Check if a solution satisfies all constraints.
        
        Args:
            x: Solution vector to check
            A_ub: Inequality constraint matrix
            b_ub: Inequality constraint vector
            A_eq: Equality constraint matrix
            b_eq: Equality constraint vector
            bounds: Variable bounds
            
        Returns:
            Dictionary containing feasibility information:
                - feasible: Boolean indicating if all constraints are satisfied
                - max_violation: Maximum constraint violation
                - inequality_violations: List of inequality constraint violations
                - equality_violations: List of equality constraint violations
                - bound_violations: List of bound violations
        """
        x_arr = np.asarray(x, dtype=float)
        
        # Check inequality constraints
        inequality_violations = []
        max_ineq_violation = 0.0
        
        if A_ub is not None and b_ub is not None:
            A_ub_arr = np.asarray(A_ub, dtype=float)
            b_ub_arr = np.asarray(b_ub, dtype=float)
            
            residuals = A_ub_arr @ x_arr - b_ub_arr
            for i, residual in enumerate(residuals):
                if residual > self.tolerance:
                    inequality_violations.append({
                        'constraint': i,
                        'violation': float(residual),
                        'type': 'inequality'
                    })
                    max_ineq_violation = max(max_ineq_violation, residual)
        
        # Check equality constraints
        equality_violations = []
        max_eq_violation = 0.0
        
        if A_eq is not None and b_eq is not None:
            A_eq_arr = np.asarray(A_eq, dtype=float)
            b_eq_arr = np.asarray(b_eq, dtype=float)
            
            residuals = A_eq_arr @ x_arr - b_eq_arr
            for i, residual in enumerate(residuals):
                violation = abs(residual)
                if violation > self.tolerance:
                    equality_violations.append({
                        'constraint': i,
                        'violation': float(violation),
                        'type': 'equality'
                    })
                    max_eq_violation = max(max_eq_violation, violation)
        
        # Check bounds
        bound_violations = []
        max_bound_violation = 0.0
        
        if bounds is not None:
            for i, (lower, upper) in enumerate(bounds):
                value = x_arr[i]
                
                if lower is not None and value < lower - self.tolerance:
                    violation = lower - value
                    bound_violations.append({
                        'variable': i,
                        'violation': float(violation),
                        'type': 'lower_bound',
                        'bound': float(lower),
                        'value': float(value)
                    })
                    max_bound_violation = max(max_bound_violation, violation)
                
                if upper is not None and value > upper + self.tolerance:
                    violation = value - upper
                    bound_violations.append({
                        'variable': i,
                        'violation': float(violation),
                        'type': 'upper_bound',
                        'bound': float(upper),
                        'value': float(value)
                    })
                    max_bound_violation = max(max_bound_violation, violation)
        
        max_violation = max(max_ineq_violation, max_eq_violation, max_bound_violation)
        feasible = (max_violation <= self.tolerance)
        
        return {
            'feasible': feasible,
            'max_violation': float(max_violation),
            'inequality_violations': inequality_violations,
            'equality_violations': equality_violations,
            'bound_violations': bound_violations,
            'tolerance': self.tolerance
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def solve_lp_problem(
    c: Vector,
    A_ub: Optional[Matrix] = None,
    b_ub: Optional[Vector] = None,
    bounds: Optional[Bounds] = None,
    maximize: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to solve a standard LP problem.
    
    Args:
        c: Objective coefficients
        A_ub: Inequality constraint matrix
        b_ub: Inequality constraint vector
        bounds: Variable bounds
        maximize: Whether to maximize (True) or minimize (False)
        
    Returns:
        Dictionary containing solution results
    """
    solver = LPSolver()
    return solver.solve(c=c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, maximize=maximize)


def solve_lp_from_matrices(
    lp_matrices: Dict[str, Any],
    maximize: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to solve LP from pre-built matrices.
    
    Args:
        lp_matrices: Dictionary containing LP matrices
        maximize: Whether to maximize (True) or minimize (False)
        
    Returns:
        Dictionary containing solution results
    """
    solver = LPSolver()
    return solver.solve_from_matrices(lp_matrices, maximize)


# ============================================================================
# ERROR HANDLING
# ============================================================================

class LPSolverError(Exception):
    """Base exception for LP solver errors."""
    pass


class InfeasibleProblemError(LPSolverError):
    """Exception raised when LP problem is infeasible."""
    pass


class UnboundedProblemError(LPSolverError):
    """Exception raised when LP problem is unbounded."""
    pass


class NumericalError(LPSolverError):
    """Exception raised when numerical issues occur during solving."""
    pass


# =