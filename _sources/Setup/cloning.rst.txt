.. _setup_git_cloning:

===================================
Before you clone the GIT repository
===================================

#. Create a github account:

   https://github.com/

#. On the Linux machine that you will clone the github from, generate a SSH key (if not already done)

   https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/

#. Add a new SSH key to your GitHub account

   https://help.github.com/articles/adding-a-new-ssh-key-to-your-github-account/

#. Verify that you have git version 2.13.0 (or later) installed

   .. code-block:: bash

     $ git version
     git version 2.13.0


#. Verify that you have git-lfs version 2.1.1 (or later) installed

   .. code-block:: bash

     $ git-lfs version
     git-lfs/2.1.1


#. Setup for large filesystems on github (one-time step). The --skip-repo is a workaround due to a bug in LFS that shows a warning message that could be interpreted as an error message.   

   .. code-block:: bash

     $ git lfs install --skip-repo
