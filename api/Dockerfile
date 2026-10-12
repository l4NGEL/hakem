FROM eclipse-temurin:17-jdk AS build
WORKDIR /src
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN chmod +x mvnw && ./mvnw -q -B dependency:go-offline
COPY src src
RUN ./mvnw -q -B package -DskipTests

FROM eclipse-temurin:17-jre
RUN useradd --system --uid 10001 app
WORKDIR /app
COPY --from=build /src/target/api-*.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "app.jar"]
