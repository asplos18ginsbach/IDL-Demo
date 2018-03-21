# IDL Demo

## Introduction

This is a gui to demonstrate the Idiom Description Language (IDL). Please refer to [Philip Ginsbach, Toomas Remmelg, Michel Steuwer, Bruno Bodin, Christophe Dubach and Michael O’Boyle. Automatic Matching of Legacy Code to Heterogeneous APIs: An Idiomatic Approach. 23rd ACM International Conference on Architectural Support for Programming Languages and Operating Systems](https://www.asplos2018.org/program/) for details.

## Dependencies

* Everything required to build [llvm and clang](https://llvm.org/docs/GettingStarted.html#software)
* [Python 2.7](https://www.python.org) with [GTK+3 bindings](http://python-gtk-3-tutorial.readthedocs.io/en/latest/install.html)
* [ninja](https://ninja-build.org)
* [ghc](https://www.haskell.org/ghc)
* [pypy](https://pypy.org)

## Installation

Please set up the gui directory as follows:

```sh
git clone https://github.com/asplos18ginsbach/IDL-Demo
cd IDL-Demo
git clone https://github.com/asplos18ginsbach/llvm
cd llvm/tools
git clone https://github.com/asplos18ginsbach/clang
cd ../..
mkdir build
cd build
cmake ../llvm -DCMAKE_BUILD_TYPE=RELEASE -GNinja -DLLVM_PARALLEL_LINK_JOBS=1
ninja
```

## Usage

On the left side, enter valid C++ code. Load existing files into the editor using _File->Open_.
Selecting _Compiler->Compile_ will run this code through a modified version of clang that implements compiler analyses using the IDL programming language.
The progress can be observed in the message box at the bottom.

As a result of running _Compiler->Compile_, LLVM IR will appear in the _compiler IR code_ tab and the detected instances will appear in the _detection results_ tab.
By default, the program will look for reductions, histograms and matrix multiplications.

![Screenshot of IDL GUI](https://github.com/cc18ginsbach/CAnDL-Demo/raw/master/idl_gui_screenshot.jpg?raw=true "IDL GUI")

## Contact

If you have further questions, please contact me at philip.ginsbach@ed.ac.uk.

