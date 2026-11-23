\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{jcsa}[2024/01/01 v1.2 Journal of Computational Surface Analysis]
\LoadClass[10pt,twocolumn]{article}
\RequirePackage{graphicx}
\def\@journalname{}
\newcommand{\journalname}[1]{\gdef\@journalname{#1}}
\def\@keywords{}
\newcommand{\keywords}[1]{\gdef\@keywords{#1}}
\renewcommand{\maketitle}{%
  \ifx\@journalname\@empty
    \ClassError{jcsa}{\string\journalname\space is required by the JCSA template}{Add \string\journalname{...} to the preamble.}%
  \fi
  \twocolumn[{\centering{\Large\bfseries\@title\par}\vskip 1em{\@author\par}\vskip .5em{\small\itshape\@journalname\par}\vskip 1em}]}
\AtEndDocument{\ifx\@keywords\@empty\ClassWarningNoLine{jcsa}{No \string\keywords\space given}\fi}
