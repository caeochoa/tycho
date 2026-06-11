%% awesome-cv.cls — Minimal pdfLaTeX class for Awesome CV template
%% No XeLaTeX dependency. Companion to cv.tex.j2.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{awesome-cv}[2024/01/01 Awesome CV class]

\LoadClass[10pt,a4paper]{article}

%% ---------- Packages ----------
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}
\RequirePackage[
  top=1.5cm, bottom=1.2cm, left=1.8cm, right=1.8cm
]{geometry}
\RequirePackage{xcolor}
\RequirePackage[hidelinks]{hyperref}
\RequirePackage{longtable}
\RequirePackage{enumitem}
\RequirePackage{graphicx}
\RequirePackage{tikz}

%% ---------- ATS essentials ----------
\input{glyphtounicode}
\pdfgentounicode=1

%% ---------- Layout defaults ----------
\pagestyle{empty}
\setlength{\parindent}{0mm}
\setlength{\tabcolsep}{0pt}
\setlength{\LTpre}{0pt}
\setlength{\LTpost}{0pt}

%% ---------- Compact itemize ----------
\setlist[itemize]{leftmargin=3.5mm, noitemsep, topsep=1pt}
\renewcommand\labelitemi{$\vcenter{\hbox{\tiny$\bullet$}}$}

%% ---------- Section heading ----------
%% Uses \accentcolor defined per-document in the .tex file.
\newcommand{\cvsect}[1]{%
  \vspace{0.6\baselineskip}%
  {\large\textcolor{accentcolor}{\textbf{\MakeUppercase{#1}}}}%
  \par\vspace{1pt}%
  {\color{accentcolor}\hrule height 0.6pt}%
  \vspace{4pt}%
}

%% ---------- Skill separator ----------
\newcommand{\slashsep}{%
  \hspace{2mm}{\textcolor{accentcolor}{/}}\hspace{2mm}%
}
