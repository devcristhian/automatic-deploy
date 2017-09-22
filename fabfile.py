from __future__ import with_statement
import os
from time import time
from StringIO import StringIO
from tempfile import NamedTemporaryFile

from fabric.api import local, env, run, cd, get
from fabric.decorators import task
from fabric.contrib.files import exists, upload_template

env.use_ssh_config = True
env.hosts = ['siis']

releases_dir = "/var/www/html/releases"
git_branch = "master"
git_repo = "git@github.com:ClinicaColombia/siis.git"
repo_dir = "/var/www/html/repo"
persist_dir = "/var/www/html/persist"
next_release = "%(time).0f" % {'time': time()}
current_release = "/var/www/html/current"
last_release_file = "/var/www/html/LAST_RELEASE"
current_release_file = "/var/www/html/CURRENT_RELEASE"

@task
def deploy():
    init()
    update_git()
    create_release()
    swap_symlinks()

@task
def rollback():
    last_release = get_last_release()
    current_release = get_current_release()

    rollback_release(last_release)

    write_last_release(current_release)
    write_current_release(last_release)

def get_last_release():
    fd = StringIO()
    get(last_release_file, fd)
    return fd.getvalue()

def get_current_release():
    fd = StringIO()
    get(current_release_file, fd)
    return fd.getvalue()

def write_last_release(last_release):
    last_release_tmp = NamedTemporaryFile(delete=False)
    last_release_tmp.write("%(release)s")
    last_release_tmp.close()

    upload_template(last_release_tmp.name, last_release_file, {'release':last_release}, backup=False)
    os.remove(last_release_tmp.name)

def write_current_release(current_release):
    current_release_tmp = NamedTemporaryFile(delete=False)
    current_release_tmp.write("%(release)s")
    current_release_tmp.close()

    upload_template(current_release_tmp.name, current_release_file, {'release':current_release}, backup=False)
    os.remove(current_release_tmp.name)

def rollback_release(to_release):
    release_into = "%s/%s" % (releases_dir, to_release)
    run("ln -nfs %s %s" % (release_into, current_release))
    run("sudo /bin/systemctl reload httpd.service")
    run("sudo /bin/systemctl status httpd.service")

def init():
    if not exists(releases_dir):
        run("mkdir -p %s" % releases_dir)

    if not exists(repo_dir):
        run("git clone -b %s %s %s" % (git_branch, git_repo, repo_dir))

    if not exists(persist_dir):
        run("mkdir -p %s/cache" % persist_dir)
        run("mkdir -p %s/tmp" % persist_dir)
        run("mkdir -p %s/rips" % persist_dir)
        run("mkdir -p %s/logs" % persist_dir)

def update_git():
    with cd(repo_dir): #  La ruta donde tenemos el proyecto
        run("git checkout %s" % git_branch)
        run("git pull origin %s" % git_branch)

def create_release():
    release_into = "%s/%s" % (releases_dir, next_release)
    run("mkdir -p %s" % release_into)
    with cd(repo_dir):
        run("git archive --worktree-attributes %s | tar -x -C %s" % (git_branch, release_into))

def swap_symlinks():
    release_into = "%s/%s" % (releases_dir, next_release)
    # rm -fr /var/www/html/releases/154852368/cache/
    run("rm -rf %s/cache" % release_into)
    run("rm -rf %s/tmp" % release_into)
    run("rm -rf %s/rips" % release_into)
    run("rm -rf %s/logs" % release_into)
    # ln -nfs /var/www/html/persist/cache /var/www/html/releases/154852368/cache
    run("ln -nfs %s/cache %s/cache" % (persist_dir, release_into))
    run("ln -nfs %s/tmp %s/tmp" % (persist_dir, release_into))
    run("ln -nfs %s/rips %s/rips" % (persist_dir, release_into))
    run("ln -nfs %s/logs %s/logs" % (persist_dir, release_into))

    run("ln -nfs %s %s" % (release_into, current_release))

    write_last_release(get_current_release())

    write_current_release(next_release)

    run("sudo /bin/systemctl reload httpd.service")
    run("sudo /bin/systemctl status httpd.service")
