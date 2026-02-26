FROM alpine:3.21.3

RUN apk add --no-cache --update bash docker openjdk8

WORKDIR /workdir

COPY --chown=root:root cli/target/universal/stage /workdir

FROM alpine:3.21.3

RUN apk add --no-cache --update bash docker openjdk8

WORKDIR /workdir

COPY --chown=root:root cli/target/universal/stage /workdir

# Add a non-root user 'appuser'
RUN adduser -D appuser \
  && chown -R appuser:appuser /workdir

# Switch to the non-root user
# USER appuser

ENTRYPOINT ["/workdir/bin/codacy-analysis-cli"]

CMD []

ENTRYPOINT ["/workdir/bin/codacy-analysis-cli"]

CMD []
