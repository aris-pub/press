#set document(title: "The Spectral Theorem", author: ("Elena Rodriguez", "David Kim"))
#set text(font: "New Computer Modern", size: 11pt)
#set par(justify: true, leading: 0.65em)

#align(center)[
  #text(size: 18pt, weight: "bold")[The Spectral Theorem]

  #v(0.5em)

  Dr. Victor Frankenstein and Captain Nemo \
  Institute of Linear Transformations, Transylvania Polytechnic

  #v(0.3em)
  January 5, 2025
]

#v(1em)

= Abstract

The spectral theorem establishes that symmetric matrices can be diagonalized by orthogonal transformations. This fundamental result connects linear algebra with geometric intuition and enables applications from optimization to quantum mechanics.

_Example scroll made with Typst + Pandoc for Scroll Press._

= Introduction

The spectral theorem answers a fundamental question: when can a linear transformation be completely understood through its eigenvalues and eigenvectors? For symmetric matrices, the answer is remarkably complete—they always possess a full set of real eigenvalues with orthogonal eigenvectors.

= Main Result

#block(
  fill: rgb("#e3f2fd"),
  inset: 12pt,
  radius: 4pt,
)[
  *Theorem (Spectral Theorem for Real Symmetric Matrices).* Let $A in RR^(n times n)$ be symmetric. Then:

  1. All eigenvalues of $A$ are real.
  2. There exists an orthonormal basis of $RR^n$ consisting of eigenvectors of $A$.
  3. $A$ can be diagonalized as $A = Q Lambda Q^T$, where $Q$ is orthogonal and $Lambda$ is diagonal.
]

*Proof sketch.* By induction on $n$. Symmetric matrices have real eigenvalues (shown via conjugate transpose argument). For each eigenvalue $lambda_1$ with unit eigenvector $bold(v)_1$, extend to an orthonormal basis and consider $Q_1^T A Q_1$, which has block-diagonal form with $(n-1) times (n-1)$ symmetric block $tilde(A)$. Apply induction to $tilde(A)$ and combine orthogonal matrices.

= Example

Consider $A = mat(3, 1; 1, 3)$. The characteristic polynomial is $(lambda-4)(lambda-2)$, giving eigenvalues $lambda_1 = 4$ and $lambda_2 = 2$. Corresponding orthonormal eigenvectors are:

$ bold(v)_1 = 1/sqrt(2) mat(1; 1), quad bold(v)_2 = 1/sqrt(2) mat(1; -1) $

Thus:
$ Q = mat(1\/sqrt(2), 1\/sqrt(2); 1\/sqrt(2), -1\/sqrt(2)), quad Lambda = mat(4, 0; 0, 2) $

Verification: $Q^T A Q = Lambda$ and $A = Q Lambda Q^T$.

= Applications

*Quadratic forms*: Using $A = Q Lambda Q^T$, any quadratic form $bold(x)^T A bold(x)$ reduces to $sum_(i=1)^n lambda_i y_i^2$ in eigenvector coordinates. The signs of eigenvalues determine whether critical points are minima, maxima, or saddles.

*Principal Component Analysis*: PCA finds directions of maximum variance in data by computing eigenvectors of the covariance matrix, projecting onto top eigenvectors for dimensionality reduction.

*Differential equations*: For $bold(x)'(t) = A bold(x)(t)$ with symmetric $A$, the eigenvector decomposition decouples the system into independent modes: $y_i'(t) = lambda_i y_i(t)$, with solutions $y_i(t) = y_i(0) e^(lambda_i t)$.

= Conclusion

The spectral theorem provides both theoretical insight and computational power for symmetric matrices. The geometric interpretation—any symmetric transformation is a rotation, scaling along axes, and inverse rotation—illuminates the structure while enabling applications across mathematics, physics, and data science.

= References

1. Axler, S. (2015). *Linear Algebra Done Right* (3rd ed.). Springer.
2. Strang, G. (2016). *Introduction to Linear Algebra* (5th ed.). Wellesley-Cambridge Press.

#line(length: 100%)

#align(center)[
  #text(style: "italic")[Example scroll made with Typst + Pandoc for Scroll Press.]
]
