# Web interface

This guide will help you to setup the web interface for the bot.

## Install Certbot

```
sudo apt install certbot python3-certbot-nginx
```

## Generate Certificate

```
export MY_DOMAIN=settings.thornode.org
# or 
export MY_DOMAIN=test-settings.thornode.org

make stop
sudo certbot certonly --standalone -w ./web/frontend/ -d $MY_DOMAIN
rm -rf web/letsencrypt/$MY_DOMAIN/
cp -rL /etc/letsencrypt/live/$MY_DOMAIN/ letsencrypt/
make start
```

## Frontend

### Yarn installation

```
curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | sudo apt-key add -
echo "deb https://dl.yarnpkg.com/debian/ stable main" | sudo tee /etc/apt/sources.list.d/yarn.list
sudo apt update
sudo apt install yarn
yarn --version
```

### Frontend building

```
cd ...your temp path...
git clone https://github.com/tirinox/nodeop-settings
yarn install
yarn build

# move everything to /web/frontend
cp -r * ../../thorchainmonitorbot/web/frontend/
```
