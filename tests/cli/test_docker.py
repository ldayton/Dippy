"""Test cases for docker."""

import pytest

from conftest import is_approved, needs_confirmation

#
# ==========================================================================
# Docker
# ==========================================================================
#
TESTS = [
    ("docker ps", True),
    ("docker ps -a", True),
    ("docker ps --all", True),
    ("docker ps --format '{{.Names}}'", True),
    ("docker container ls", True),
    ("docker container ls -a", True),
    # docker images / image ls - list images
    ("docker images", True),
    ("docker images -a", True),
    ("docker images --format '{{.Repository}}'", True),
    ("docker image ls", True),
    ("docker image ls -a", True),
    # docker inspect - inspect objects
    ("docker inspect mycontainer", True),
    ("docker inspect --format '{{.State.Running}}' mycontainer", True),
    ("docker container inspect mycontainer", True),
    ("docker image inspect myimage", True),
    ("docker volume inspect myvol", True),
    ("docker network inspect mynet", True),
    # docker logs - view container logs
    ("docker logs mycontainer", True),
    ("docker logs -f mycontainer", True),
    ("docker logs --tail 100 mycontainer", True),
    ("docker logs --since 1h mycontainer", True),
    ("docker container logs mycontainer", True),
    # docker top - show processes
    ("docker top mycontainer", True),
    ("docker top mycontainer aux", True),
    ("docker container top mycontainer", True),
    # docker port - show port mappings
    ("docker port mycontainer", True),
    ("docker port mycontainer 80", True),
    # docker stats - resource usage
    ("docker stats", True),
    ("docker stats mycontainer", True),
    ("docker stats --no-stream", True),
    ("docker container stats mycontainer", True),
    # docker history - image history
    ("docker history myimage", True),
    ("docker history --no-trunc myimage", True),
    ("docker image history myimage", True),
    # docker events - real-time events
    ("docker events", True),
    ("docker events --since 1h", True),
    ("docker events --filter container=mycontainer", True),
    ("docker system events", True),
    # docker diff - filesystem changes
    ("docker diff mycontainer", True),
    ("docker container diff mycontainer", True),
    # docker version / info - system info
    ("docker version", True),
    ("docker info", True),
    ("docker system info", True),
    ("docker system df", True),
    # docker search - search Docker Hub
    ("docker search nginx", True),
    ("docker search --limit 10 nginx", True),
    # docker context - context management (read-only)
    ("docker context ls", True),
    ("docker context show", True),
    ("docker context inspect mycontext", True),
    # docker network - network inspection (read-only)
    ("docker network ls", True),
    ("docker network inspect bridge", True),
    # docker volume - volume inspection (read-only)
    ("docker volume ls", True),
    ("docker volume inspect myvol", True),
    # docker with global flags
    ("docker --host tcp://localhost:2375 ps", True),
    ("docker -H tcp://localhost:2375 ps", True),
    ("docker --context mycontext ps", True),
    ("docker -c mycontext images", True),
    ("docker --log-level debug ps", True),
    ("docker -l debug images", True),
    ("docker --config /path/to/config ps", True),
    #
    # docker - unsafe (container lifecycle)
    #
    ("docker run ubuntu", False),
    ("docker run -it ubuntu bash", False),
    ("docker run -d nginx", False),
    ("docker run --rm alpine echo hello", False),
    ("docker container run ubuntu", False),
    ("docker start mycontainer", False),
    ("docker container start mycontainer", False),
    ("docker stop mycontainer", False),
    ("docker container stop mycontainer", False),
    ("docker kill mycontainer", False),
    ("docker container kill mycontainer", False),
    ("docker restart mycontainer", False),
    ("docker container restart mycontainer", False),
    ("docker pause mycontainer", False),
    ("docker container pause mycontainer", False),
    ("docker unpause mycontainer", False),
    ("docker container unpause mycontainer", False),
    ("docker wait mycontainer", False),
    ("docker container wait mycontainer", False),
    #
    # docker - unsafe (exec runs arbitrary commands)
    #
    ("docker exec mycontainer ls", False),
    ("docker exec -it mycontainer bash", False),
    ("docker exec -u root mycontainer whoami", False),
    ("docker container exec mycontainer ls", False),
    #
    # docker - unsafe (image/container mutations)
    #
    ("docker create ubuntu", False),
    ("docker container create ubuntu", False),
    ("docker rm mycontainer", False),
    ("docker rm -f mycontainer", False),
    ("docker container rm mycontainer", False),
    ("docker rmi myimage", False),
    ("docker image rm myimage", False),
    ("docker build .", False),
    ("docker build -t myimage .", False),
    ("docker image build -t myimage .", False),
    ("docker commit mycontainer myimage", False),
    ("docker container commit mycontainer", False),
    ("docker tag myimage myrepo:tag", False),
    ("docker image tag myimage myrepo:tag", False),
    #
    # docker - unsafe (registry operations)
    #
    ("docker pull nginx", False),
    ("docker pull nginx:latest", False),
    ("docker image pull nginx", False),
    ("docker push myrepo/myimage", False),
    ("docker image push myrepo/myimage", False),
    ("docker login", False),
    ("docker login -u user", False),
    ("docker logout", False),
    #
    # docker - unsafe (file operations that modify filesystem)
    #
    ("docker cp mycontainer:/path /local", False),
    ("docker cp /local mycontainer:/path", False),
    ("docker container cp mycontainer:/path /local", False),
    ("docker import export.tar myimage", False),
    ("docker image import export.tar", False),
    ("docker load < image.tar", False),
    ("docker image load -i image.tar", False),
    #
    # docker - safe (export/save just output data to stdout, don't modify anything)
    # Note: redirects like "> file.tar" are caught by redirect detection
    #
    ("docker export mycontainer", True),
    ("docker container export mycontainer", True),
    ("docker save myimage", True),
    ("docker image save myimage", True),
    # But redirects to files are caught
    ("docker export mycontainer > export.tar", False),
    ("docker save myimage > image.tar", False),
    ("docker image save myimage -o image.tar", False),  # -o writes to file
    #
    # docker - unsafe (container modifications)
    #
    ("docker rename oldname newname", False),
    ("docker container rename oldname newname", False),
    ("docker update --memory 512m mycontainer", False),
    ("docker container update --cpus 2 mycontainer", False),
    ("docker attach mycontainer", False),
    ("docker container attach mycontainer", False),
    #
    # docker - unsafe (system operations)
    #
    ("docker system prune", False),
    ("docker system prune -a", False),
    ("docker container prune", False),
    ("docker image prune", False),
    ("docker volume prune", False),
    ("docker network prune", False),
    ("docker builder prune", False),
    #
    # docker - unsafe (network mutations)
    #
    ("docker network create mynet", False),
    ("docker network rm mynet", False),
    ("docker network connect mynet mycontainer", False),
    ("docker network disconnect mynet mycontainer", False),
    #
    # docker - unsafe (volume mutations)
    #
    ("docker volume create myvol", False),
    ("docker volume rm myvol", False),
    #
    # docker - unsafe (context mutations)
    #
    ("docker context create mycontext", False),
    ("docker context rm mycontext", False),
    ("docker context update mycontext", False),
    ("docker context use mycontext", False),
    #
    # Docker Compose
    #
    # docker compose - read-only commands are safe
    # Safe: ps, logs, config, images, top, version, ls, port, events
    # Unsafe: up, down, start, stop, exec, run, build, pull, push, rm, kill,
    #         restart, pause, unpause, create, scale, cp, attach, wait, watch
    #
    # docker compose - safe (inspection)
    ("docker compose ps", True),
    ("docker compose ps -a", True),
    ("docker compose logs", True),
    ("docker compose logs -f", True),
    ("docker compose logs web", True),
    ("docker compose config", True),
    ("docker compose config --services", True),
    ("docker compose images", True),
    ("docker compose top", True),
    ("docker compose version", True),
    ("docker compose ls", True),
    ("docker compose port web 80", True),
    ("docker compose events", True),
    # docker compose with project flags
    ("docker compose -f docker-compose.yml ps", True),
    ("docker compose --file docker-compose.yml logs", True),
    ("docker compose -p myproject ps", True),
    ("docker compose --project-name myproject logs", True),
    ("docker compose --project-directory /path ps", True),
    ("docker compose --env-file .env ps", True),
    #
    # docker compose - unsafe (lifecycle)
    #
    ("docker compose up", False),
    ("docker compose up -d", False),
    ("docker compose up --build", False),
    ("docker compose down", False),
    ("docker compose down -v", False),
    ("docker compose start", False),
    ("docker compose start web", False),
    ("docker compose stop", False),
    ("docker compose stop web", False),
    ("docker compose restart", False),
    ("docker compose restart web", False),
    ("docker compose kill", False),
    ("docker compose kill web", False),
    ("docker compose pause", False),
    ("docker compose unpause", False),
    #
    # docker compose - unsafe (exec/run)
    #
    ("docker compose exec web bash", False),
    ("docker compose exec -it web sh", False),
    ("docker compose run web echo hello", False),
    ("docker compose run --rm web pytest", False),
    #
    # docker compose - unsafe (build/registry)
    #
    ("docker compose build", False),
    ("docker compose build web", False),
    ("docker compose pull", False),
    ("docker compose pull web", False),
    ("docker compose push", False),
    ("docker compose push web", False),
    #
    # docker compose - unsafe (container management)
    #
    ("docker compose rm", False),
    ("docker compose rm -f", False),
    ("docker compose create", False),
    ("docker compose scale web=3", False),
    ("docker compose cp web:/path /local", False),
    ("docker compose attach web", False),
    ("docker compose wait web", False),
    ("docker compose watch", False),
    #
    # docker compose - unsafe (misc)
    #
    ("docker compose commit web myimage", False),
    ("docker compose export web", False),
    ("docker compose publish", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_docker(check, command: str, expected: bool) -> None:
    """Test command safety."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
