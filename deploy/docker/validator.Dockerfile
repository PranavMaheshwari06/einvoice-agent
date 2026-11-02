FROM eclipse-temurin:21-jre

# Versions match DATA_SOURCES.md; the daemon needs Java 11 or later.
ARG VALIDATOR_VERSION=1.6.3
ARG CONFIG_RELEASE=v2026-08-31
ARG CONFIG_ZIP=xrechnung-3.0.2-validator-configuration-2026-08-31.zip

RUN apt-get update \
    && apt-get install -y --no-install-recommends unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /validator
ADD --chmod=644 https://github.com/itplr-kosit/validator/releases/download/v${VALIDATOR_VERSION}/validator-${VALIDATOR_VERSION}-standalone.jar validator.jar
ADD https://github.com/itplr-kosit/validator-configuration-xrechnung/releases/download/${CONFIG_RELEASE}/${CONFIG_ZIP} config.zip
RUN unzip -q config.zip -d config

RUN useradd --system validator
USER validator

EXPOSE 8081
CMD ["java", "-jar", "validator.jar", "-s", "config/scenarios.xml", "-r", "config", \
     "-D", "-G", "-H", "0.0.0.0", "-P", "8081"]
