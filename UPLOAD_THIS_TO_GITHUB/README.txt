This folder exists only to work around a Windows quirk.

GitHub needs the workflow file at this exact path in your repository:

    .github/workflows/update-and-deploy.yml

Windows hides any folder whose name starts with a dot, which is why the
original ".github" folder was invisible when you dragged files in.

Follow the steps Claude gave you to create the folders directly on GitHub
and paste the file contents in. Nothing in this folder is used by the
website itself.
