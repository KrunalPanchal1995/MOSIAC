MSO Studio
==========

Unified PySide6 GUI integrator for the Mechanism Optimization Suite:
nominal simulation, mechanism comparison, sensitivity analysis,
optimization, mechanism-comparison automation, and curve-fitting/PDF tools
-- all with one-click LaTeX reporting.

Architecture
------------

Two layers, connected by :class:`~mso_studio.core.runrecord.RunConfig` /
:class:`~mso_studio.core.runrecord.RunRecord`:

* ``mso_studio.core`` -- pure Python, zero Qt imports. Adapters that shell
  out to this suite's existing science backends (running in the anaconda
  ``python3.9`` environment) and turn their output into ``RunRecord``
  objects.
* ``mso_studio.gui`` -- all Qt/PySide6 code, and only Qt code.

Running
-------

.. code-block:: bash

   ./scripts/setup_gui_venv.sh          # first time only
   .venv-gui/bin/python run_mso_studio.py

.. toctree::
   :maxdepth: 2
   :caption: Contents

   user_guide
   traceability
   api/core
   api/gui
