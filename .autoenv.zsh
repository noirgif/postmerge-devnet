export DEVNET_PATH=/dev/shm/devnet

alias down='killall beacon-chain geth teku validator'

function cdnode() {
    cd $DEVNET_PATH/node$1
}

function gelog() {
    less $DEVNET_PATH/node$1/geth.log
}

function valog() {
    less $DEVNET_PATH/node$1/validator.log
}

function belog() {
    less $DEVNET_PATH/node$1/beacon.log
}

if [[ -z "$VIRTUAL_ENV" ]] ; then
    poetry shell
fi
