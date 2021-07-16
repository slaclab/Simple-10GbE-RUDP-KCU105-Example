.. _requirements_git_cloning:

===================================
Before you clone the GIT repository
===================================

1) Create a github account:

https://github.com/

2) On the Linux machine that you will clone the github from, generate a SSH key (if not already done)

https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/

3) Add a new SSH key to your GitHub account

https://help.github.com/articles/adding-a-new-ssh-key-to-your-github-account/

4) Setup for large filesystems on github

.. code-block:: bash

  $ git lfs install


5) Verify that you have git version 2.13.0 (or later) installed 


.. code-block:: bash

  $ git version
  git version 2.13.0


6) Verify that you have git-lfs version 2.1.1 (or later) installed 

.. code-block:: bash

  $ git-lfs version
  git-lfs/2.1.1
