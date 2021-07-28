.. _how_to_tag_release:

==================================
How to ruckus's Tag Release Script
==================================

Ruckus provides a script to help users will tag releasing
firmware only or firmware/software combinations.  The firmware images
can be attached to the tag release such that you do not have to
commit the binary files into the git repository. This enables the
users to be able to have the same git hash for the both the
git tag and the firmware binary images.  For more information
please refer to the presentation below:

https://docs.google.com/presentation/d/1D6rwhGMM1HEm3o1AO5YKfpZ1SmLPQVzcC5GOk5vnc84/edit?usp=sharing

A **releases.yaml** file is used to define the location of all the firmware/software configurations
and files that will be included in the tag release via the ruckus script.  Here is where this
YAML file is located for this project:

https://github.com/slaclab/Simple-10GbE-RUDP-KCU105-Example/blob/main/firmware/releases.yaml

How to create a tag release
===========================

#. Setup Xilinx licensing (refer to :ref:`setup_vivado_setup`)

#. Go to the target directory

   .. code-block:: bash

      $ cd Simple-10GbE-RUDP-KCU105-Example/firmware/targets/Simple10GbeRudpKcu105Example

#. Optional: build only the release files without doing a tag

   .. code-block:: bash

      $ make release_files

#. Make the tag release and include the firmware attachments

   .. code-block:: bash

      $ make release
